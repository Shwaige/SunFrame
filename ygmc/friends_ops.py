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
    errors: int = 0


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


def extract_one_key_links(page: str, excluded_keywords: tuple[str, ...] = ()) -> list[str]:
    return extract_one_key_links_by_text(page, excluded_keywords=excluded_keywords)


def extract_one_key_links_by_text(
    page: str,
    allowed_keywords: tuple[str, ...] = (),
    excluded_keywords: tuple[str, ...] = (),
) -> list[str]:
    section = extract_one_key_section(page)
    if not section:
        return []
    links: list[str] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", section, re.I | re.S):
        plain = _clean_text(text)
        if allowed_keywords and not any(keyword in plain for keyword in allowed_keywords):
            continue
        if any(keyword in plain for keyword in excluded_keywords):
            continue
        links.append(html.unescape(href))
    return links


def extract_one_key_section(page: str) -> str:
    match = re.search(r"一键：(.*?)(?:<br\s*/?>|\n)", page, re.I | re.S)
    return match.group(1) if match else ""


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
    if kind == "farm":
        return bool(extract_one_key_links_by_text(page, ("摘取", "摘菜", "帮助"), ("放虫",)))
    return bool(extract_one_key_links(page))


def extract_farm_single_links(page: str, allowed_actions: tuple[str, ...] | None = None) -> list[str]:
    allowed = allowed_actions or ("摘取", "摘菜", "浇水", "除草", "帮助")
    links: list[str] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        href = html.unescape(href)
        plain_action = plain.strip("[]")
        if "friendOperate.go" in href and plain_action in allowed:
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


def _ranch_is_open(client: HttpClient, params: dict[str, str]) -> bool:
    page = client.fetch("/ygmc/home/index.go", {**params, "indexType": "1"})
    text = _clean_text(page)
    if "农场10级开放" in text or "请努力升级再来" in text or "未开通" in text:
        return False
    return "畜牧场等级" in text or "我的畜牧场" in text or "动物" in text or "饲料" in text


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _fetch_with_retry(client: HttpClient, path: str, params: dict[str, str] | None = None) -> str:
    try:
        return client.fetch(path, params)
    except TimeoutError:
        return client.fetch(path, params)


def _run_farm_round(client: HttpClient, params: dict[str, str]) -> tuple[int, int]:
    done = 0
    errors = 0
    first_page = _fetch_with_retry(client, "/ygmc/farm/myFriends.go", params)
    total_pages = parse_total_pages(first_page)
    for page_no in range(1, total_pages + 1):
        try:
            current_page = (
                first_page
                if page_no == 1
                else _fetch_with_retry(client, "/ygmc/farm/myFriends.go", {**params, "pageNo": str(page_no)})
            )
        except Exception as exc:
            errors += 1
            print(f"农场好友页处理失败=页码={page_no}|错误={_error_text(exc)}")
            continue
        for friend in parse_friend_list(current_page, "farm"):
            if friend["tag"] not in ("[可摘取]", "[可操作]"):
                continue
            try:
                detail_page = _fetch_with_retry(client, "/ygmc/farm/friendFields.go", {**params, "otherId": friend["other_id"]})
                if one_key_available(detail_page, "farm"):
                    one_key_links = extract_one_key_links_by_text(detail_page, ("摘取", "摘菜", "帮助"), ("放虫",))
                    result_pages = [_fetch_with_retry(client, link) for link in one_key_links]
                    failed = any(one_key_failed(page) for page in result_pages)
                    if failed:
                        single_links = extract_farm_single_links(detail_page)
                        for link in single_links:
                            _fetch_with_retry(client, link)
                else:
                    single_links = extract_farm_single_links(detail_page)
                    for link in single_links:
                        _fetch_with_retry(client, link)
                done += 1
            except Exception as exc:
                errors += 1
                print(f"农场好友处理失败={friend['nickname']}|状态={friend['tag']}|页码={page_no}|错误={_error_text(exc)}")
    return done, errors


def _run_ranch_round(client: HttpClient, params: dict[str, str]) -> tuple[int, int]:
    done = 0
    errors = 0
    first_page = _fetch_with_retry(client, "/ygmc/ranch/myFriends.go", params)
    total_pages = parse_total_pages(first_page)
    for page_no in range(1, total_pages + 1):
        try:
            current_page = (
                first_page
                if page_no == 1
                else _fetch_with_retry(client, "/ygmc/ranch/myFriends.go", {**params, "pageNo": str(page_no)})
            )
        except Exception as exc:
            errors += 1
            print(f"畜牧场好友页处理失败=页码={page_no}|错误={_error_text(exc)}")
            continue
        for friend in parse_friend_list(current_page, "ranch"):
            if friend["tag"] not in ("[可捉取]", "[可操作]"):
                continue
            try:
                detail_page = _fetch_with_retry(client, "/ygmc/ranch/friendSites.go", {**params, "otherId": friend["other_id"]})
                if one_key_available(detail_page, "ranch"):
                    one_key_links = extract_one_key_links(detail_page)
                    result_pages = [_fetch_with_retry(client, link) for link in one_key_links]
                    failed = any(one_key_failed(page) for page in result_pages)
                    if failed:
                        single_links = extract_ranch_single_links(client, detail_page)
                        for link in single_links:
                            _fetch_with_retry(client, link)
                else:
                    single_links = extract_ranch_single_links(client, detail_page)
                    for link in single_links:
                        _fetch_with_retry(client, link)
                done += 1
            except Exception as exc:
                errors += 1
                print(f"畜牧场好友处理失败={friend['nickname']}|状态={friend['tag']}|页码={page_no}|错误={_error_text(exc)}")
    return done, errors


def run_friends_ops(account: Account) -> FriendsOpsResult:
    game_account, credential_source = resolve_game_account(account)
    client, params, farm_list_page, ranch_list_page = _fetch_friend_pages(game_account)
    if credential_source == "cache" and account.has_login_credentials:
        if _friends_state_looks_abnormal(farm_list_page, ranch_list_page):
            game_account, credential_source = refresh_game_account(account)
            client, params, farm_list_page, ranch_list_page = _fetch_friend_pages(game_account)

    farm_done = 0
    farm_errors = 0
    for _ in range(5):
        round_done, round_errors = _run_farm_round(client, params)
        farm_done += round_done
        farm_errors += round_errors
        if round_done == 0:
            break

    ranch_done = 0
    ranch_errors = 0
    ranch_open = _ranch_is_open(client, params)
    if not ranch_open:
        print("畜牧场=未开通，已跳过")
    else:
        for _ in range(5):
            round_done, round_errors = _run_ranch_round(client, params)
            ranch_done += round_done
            ranch_errors += round_errors
            if round_done == 0:
                break

    errors = farm_errors + ranch_errors
    if farm_done == 0 and ranch_done == 0 and errors == 0:
        print("好友操作=未进行实际操作")
    else:
        if farm_done:
            print(f"农场好友处理数量={farm_done}")
        if ranch_open and ranch_done:
            print(f"畜牧场好友处理数量={ranch_done}")
        print(f"好友处理失败数量={errors}")
    return FriendsOpsResult(errors == 0, credential_source, farm_done, ranch_done, errors)
