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
    found_newcomer_red_packet: bool
    free_claim_status: str


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return html.unescape(text).replace("\r", "").replace("\n", "").strip()


def _extract_newcomer_red_packet_link(page: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if "新人红包" in plain:
            return html.unescape(href)
    return None


def _extract_free_claim_link(page: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if "免费领取" in plain:
            return html.unescape(href)
    return None


def _extract_free_claim_text(page: str) -> str:
    match = re.search(r"(每天免费领取[:：]\s*\d+/\d+)", page)
    if match:
        return _clean_text(match.group(1))
    if "免费领取次数已用完" in page:
        return "免费领取次数已用完"
    return ""


def _activity_page_looks_abnormal(page: str) -> bool:
    text = _clean_text(page)
    return "活动" not in text and "新人红包" not in text and "免费领取" not in text


def run_activity(account: Account) -> ActivityResult:
    game_account, credential_source = resolve_game_account(account)
    params = {"openId": game_account.open_id, "sid": game_account.sid}
    client = HttpClient()

    home_page = client.fetch(HOME_PATH, params)
    activity_link = _extract_newcomer_red_packet_link(home_page)

    if not activity_link and credential_source == "cache" and account.has_login_credentials:
        game_account, credential_source = refresh_game_account(account)
        params = {"openId": game_account.open_id, "sid": game_account.sid}
        client = HttpClient()
        home_page = client.fetch(HOME_PATH, params)
        activity_link = _extract_newcomer_red_packet_link(home_page)

    if not activity_link:
        print("活动检查=主页未发现新人红包")
        return ActivityResult(True, credential_source, False, "not_found")

    print("活动检查=主页发现新人红包")
    activity_page = client.fetch(activity_link)
    if _activity_page_looks_abnormal(activity_page) and account.has_login_credentials:
        game_account, credential_source = refresh_game_account(account)
        params = {"openId": game_account.open_id, "sid": game_account.sid}
        client = HttpClient()
        home_page = client.fetch(HOME_PATH, params)
        activity_link = _extract_newcomer_red_packet_link(home_page)
        if not activity_link:
            print("活动检查=刷新凭证后未发现新人红包")
            return ActivityResult(True, credential_source, False, "not_found")
        activity_page = client.fetch(activity_link)

    free_claim_text = _extract_free_claim_text(activity_page)
    free_claim_link = _extract_free_claim_link(activity_page)

    if free_claim_text:
        print(f"新人红包状态={free_claim_text}")

    if "免费领取次数已用完" in activity_page:
        print("新人红包领取=今日免费次数已用完")
        return ActivityResult(True, credential_source, True, "used_up")

    if free_claim_link:
        client.fetch(free_claim_link)
        print("新人红包领取=已点击一次免费领取")
        return ActivityResult(True, credential_source, True, "claimed_once")

    print("新人红包领取=未发现免费领取按钮")
    return ActivityResult(True, credential_source, True, "no_button")
