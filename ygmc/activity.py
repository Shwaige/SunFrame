import html
import re
from dataclasses import dataclass

from ygmc.config import Account, HOME_PATH
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account


@dataclass
class ActivityResult:
    ok: bool
    credential_source: str
    newcomer_red_packet_status: str
    mother_day_status: str


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return html.unescape(text).replace("\r", "").replace("\n", "").strip()


def _extract_activity_link(page: str, keyword: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if keyword in plain:
            return html.unescape(href)
    return None


def _extract_links_by_text(page: str, keyword: str) -> list[str]:
    links: list[str] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if keyword in plain:
            links.append(html.unescape(href))
    return links


def _extract_free_claim_text(page: str) -> str:
    match = re.search(r"(每天免费领取[:：]\s*\d+/\d+)", page)
    if match:
        return _clean_text(match.group(1))
    if "免费领取次数已用完" in page:
        return "免费领取次数已用完"
    return ""


def _run_newcomer_red_packet(client: HttpClient, home_page: str) -> str:
    activity_link = _extract_activity_link(home_page, "新人红包")
    if not activity_link:
        return "not_found"

    activity_page = client.fetch(activity_link)
    free_claim_links = _extract_links_by_text(activity_page, "免费领取")

    if "免费领取次数已用完" in activity_page:
        return "used_up"

    if free_claim_links:
        client.fetch(free_claim_links[0])
        return "claimed_once"

    return "no_button"


def _has_real_activity_action(newcomer_red_packet_status: str, mother_day_status: str) -> bool:
    return newcomer_red_packet_status == "claimed_once" or mother_day_status.startswith("clicked_")


def _newcomer_summary(status: str) -> str:
    mapping = {
        "not_found": "未发现入口",
        "used_up": "今日已用完",
        "claimed_once": "已领取一次",
        "no_button": "无可点击按钮",
    }
    return mapping.get(status, status)





def run_activity(account: Account) -> ActivityResult:
    game_account, credential_source = resolve_game_account(account)
    params = {"openId": game_account.open_id, "sid": game_account.sid}
    client = HttpClient()
    home_page = client.fetch(HOME_PATH, params)

    if credential_source == "cache" and account.has_login_credentials:
        if "牧场" not in _clean_text(home_page):
            game_account, credential_source = refresh_game_account(account)
            params = {"openId": game_account.open_id, "sid": game_account.sid}
            client = HttpClient()
            home_page = client.fetch(HOME_PATH, params)

    newcomer_red_packet_status = _run_newcomer_red_packet(client, home_page)
    if not _has_real_activity_action(newcomer_red_packet_status):
        print("活动模块=未进行实际操作")
    else:
        print(f"新人红包={_newcomer_summary(newcomer_red_packet_status)}")
    return ActivityResult(True, credential_source, newcomer_red_packet_status)
