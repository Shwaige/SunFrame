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
        print("活动检查=主页未发现新人红包")
        return "not_found"

    print("活动检查=主页发现新人红包")
    activity_page = client.fetch(activity_link)
    free_claim_text = _extract_free_claim_text(activity_page)
    free_claim_links = _extract_links_by_text(activity_page, "免费领取")

    if free_claim_text:
        print(f"新人红包状态={free_claim_text}")

    if "免费领取次数已用完" in activity_page:
        print("新人红包领取=今日免费次数已用完")
        return "used_up"

    if free_claim_links:
        client.fetch(free_claim_links[0])
        print("新人红包领取=已点击一次免费领取")
        return "claimed_once"

    print("新人红包领取=未发现免费领取按钮")
    return "no_button"


def _run_mother_day_activity(client: HttpClient, params: dict[str, str]) -> str:
    print("活动检查=进入母亲节活动")
    activity_page = client.fetch("/ygmc/summerParty/index.go", params)
    energy_links = _extract_links_by_text(activity_page, "补充体力")
    if not energy_links:
        print("母亲节活动=未发现可点击的补充体力")
        return "no_button"

    clicked = 0
    for link in energy_links[:2]:
        client.fetch(link)
        clicked += 1
    print(f"母亲节活动=已点击补充体力 {clicked} 次")
    return f"clicked_{clicked}"


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
    mother_day_status = _run_mother_day_activity(client, params)
    return ActivityResult(True, credential_source, newcomer_red_packet_status, mother_day_status)
