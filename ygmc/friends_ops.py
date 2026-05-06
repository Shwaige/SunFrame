import html
import re
from dataclasses import dataclass

from ygmc.config import Account
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account


@dataclass
class FriendsOpsResult:
    ok: bool
    credential_source: str
    farm_done: int
    ranch_done: int


def _mode_label(value: str) -> str:
    mapping = {
        "one_key": "一键",
        "single": "单次",
    }
    return mapping.get(value, value)


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return html.unescape(text).replace("\r", "").replace("\n", "").strip()


def parse_friend_list(page: str, kind: str) -> list[dict[str, str]]:
    path = "friendFields.go" if kind == "farm" else "friendSites.go"
    friends: list[dict[str, str]] = []
    pattern = re.compile(
        rf"(\d+)\.\s*<a href='[^']*{path}[^']*otherId=([a-f0-9]+)'>(.*?)</a>\s*(\[[^]]+\])?",
        re.S,
    )
    for match in pattern.finditer(page):
        _, other_id, nickname, tag = match.groups()
        friends.append(
            {
                "other_id": other_id,
                "nickname": _clean_text(nickname),
                "tag": _clean_text(tag or ""),
            }
        )
    return friends


def parse_total_pages(page: str) -> int:
    match = re.search(r"第(\d+)/(\d+)页", page)
    if not match:
        return 1
    return int(match.group(2))


def extract_links(page: str, keywords: list[str]) -> list[str]:
    links: list[str] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if any(keyword in plain for keyword in keywords):
            links.append(html.unescape(href))
    return links


def extract_one_key_links(page: str) -> list[str]:
    match = re.search(r"一键：(.*?)(?:<br\s*/?>|\n)", page, re.I | re.S)
    if not match:
        return []
    section = match.group(1)
    links: list[str] = []
    for href in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"]", section, re.I):
        links.append(html.unescape(href))
    return links


def one_key_failed(page: str) -> bool:
    failure_markers = [
        "没有可操作",
        "没有可摘取",
        "没有可捉取",
        "没有可帮助",
        "没有可帮",
        "操作失败",
        "不能操作",
        "次数不足",
        "不可操作",
        "暂无可",
    ]
    text = _clean_text(page)
    return any(marker in text for marker in failure_markers)


def one_key_available(page: str, kind: str) -> bool:
    text = _clean_text(page)
    if "开启 (无)" in text or "一键：开启(无)" in text or "一键：开启 (无)" in text:
        return False
    return bool(extract_one_key_links(page))


def extract_farm_single_links(page: str) -> list[str]:
    links: list[str] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        href = html.unescape(href)
        if "friendOperate.go" in href and plain in ("[摘取]", "[浇水]", "[除草]", "[捉虫]"):
            links.append(href)
    return links


def extract_ranch_single_links(client: HttpClient, detail_page: str) -> list[str]:
    links: list[str] = []
    site_detail_links = [
        html.unescape(href)
        for href in re.findall(r"<a\s+href=['\"]([^'\"]*friSiteDetail\.go[^'\"]*)['\"]", detail_page, re.I)
    ]
    for link in site_detail_links:
        site_page = client.fetch(link)
        for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", site_page, re.I | re.S):
            plain = _clean_text(text)
            href = html.unescape(href)
            if plain in ("[捉取]", "[帮助]", "捉取", "帮助"):
                links.append(href)
    return links


def _fetch_friend_pages(account: Account) -> tuple[HttpClient, dict[str, str], str, str]:
    params = {"openId": account.open_id, "sid": account.sid}
    client = HttpClient()
    farm_list_page = client.fetch("/ygmc/farm/myFriends.go", params)
    ranch_list_page = client.fetch("/ygmc/ranch/myFriends.go", params)
    return client, params, farm_list_page, ranch_list_page


def _friends_state_looks_abnormal(farm_list_page: str, ranch_list_page: str) -> bool:
    farm_friends = parse_friend_list(farm_list_page, "farm")
    ranch_friends = parse_friend_list(ranch_list_page, "ranch")
    return not farm_friends and not ranch_friends


def run_friends_ops(account: Account) -> FriendsOpsResult:
    game_account, credential_source = resolve_game_account(account)
    client, params, farm_list_page, ranch_list_page = _fetch_friend_pages(game_account)
    if credential_source == "cache" and account.has_login_credentials:
        if _friends_state_looks_abnormal(farm_list_page, ranch_list_page):
            game_account, credential_source = refresh_game_account(account)
            client, params, farm_list_page, ranch_list_page = _fetch_friend_pages(game_account)

    farm_done = 0
    farm_total_pages = parse_total_pages(farm_list_page)
    for page_no in range(1, farm_total_pages + 1):
        current_page = (
            farm_list_page
            if page_no == 1
            else client.fetch("/ygmc/farm/myFriends.go", {**params, "pageNo": str(page_no)})
        )
        for friend in parse_friend_list(current_page, "farm"):
            if friend["tag"] not in ("[可摘取]", "[可操作]"):
                continue
            detail_page = client.fetch("/ygmc/farm/friendFields.go", {**params, "otherId": friend["other_id"]})
            action_count = 0
            mode = "single"
            if one_key_available(detail_page, "farm"):
                one_key_links = extract_one_key_links(detail_page)
                result_pages = [client.fetch(link) for link in one_key_links]
                failed = any(one_key_failed(page) for page in result_pages)
                action_count = len(one_key_links)
                mode = "one_key"
                if failed:
                    single_links = extract_farm_single_links(detail_page)
                    for link in single_links:
                        client.fetch(link)
                    action_count = len(single_links)
                    mode = "single"
            else:
                single_links = extract_farm_single_links(detail_page)
                for link in single_links:
                    client.fetch(link)
                action_count = len(single_links)
            print(
                f"农场好友已处理={friend['nickname']}|状态={friend['tag']}|模式={_mode_label(mode)}|动作数={action_count}|页码={page_no}"
            )
            farm_done += 1

    ranch_done = 0
    ranch_total_pages = parse_total_pages(ranch_list_page)
    for page_no in range(1, ranch_total_pages + 1):
        current_page = (
            ranch_list_page
            if page_no == 1
            else client.fetch("/ygmc/ranch/myFriends.go", {**params, "pageNo": str(page_no)})
        )
        for friend in parse_friend_list(current_page, "ranch"):
            if friend["tag"] not in ("[可捉取]", "[可操作]"):
                continue
            detail_page = client.fetch("/ygmc/ranch/friendSites.go", {**params, "otherId": friend["other_id"]})
            action_count = 0
            mode = "single"
            if one_key_available(detail_page, "ranch"):
                one_key_links = extract_one_key_links(detail_page)
                result_pages = [client.fetch(link) for link in one_key_links]
                failed = any(one_key_failed(page) for page in result_pages)
                action_count = len(one_key_links)
                mode = "one_key"
                if failed:
                    single_links = extract_ranch_single_links(client, detail_page)
                    for link in single_links:
                        client.fetch(link)
                    action_count = len(single_links)
                    mode = "single"
            else:
                single_links = extract_ranch_single_links(client, detail_page)
                for link in single_links:
                    client.fetch(link)
                action_count = len(single_links)
            print(
                f"畜牧场好友已处理={friend['nickname']}|状态={friend['tag']}|模式={_mode_label(mode)}|动作数={action_count}|页码={page_no}"
            )
            ranch_done += 1

    print(f"农场好友处理数量={farm_done}")
    print(f"畜牧场好友处理数量={ranch_done}")
    return FriendsOpsResult(True, credential_source, farm_done, ranch_done)
