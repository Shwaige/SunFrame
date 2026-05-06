import html
import re
from dataclasses import dataclass

from ygmc.config import Account, BASE_URL, HOME_PATH, SIGN_PATH
from ygmc.http import HttpClient
from ygmc.output import print_summary
from ygmc.session import refresh_game_account, resolve_game_account


@dataclass
class SignResult:
    ok: bool
    credential_source: str
    result: str
    reward: str


def extract_sign_action(page: str) -> str | None:
    candidates = re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S)
    for href, text in candidates:
        plain = re.sub(r"<.*?>", "", text)
        plain = html.unescape(plain).strip()
        href = html.unescape(href)
        if "已签" in plain or "补签" in plain:
            continue
        if "签到" in plain:
            return href
    return None


def extract_reward_actions(page: str) -> list[str]:
    actions: list[str] = []
    candidates = re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S)
    for href, text in candidates:
        plain = re.sub(r"<.*?>", "", text)
        plain = html.unescape(plain).strip()
        href = html.unescape(href)
        if "领取累签" in plain or "领取月累签" in plain:
            actions.append(href)
    return actions


def is_signed(page: str) -> bool:
    return "今天签到:已签" in page or "今天签到：已签" in page


def sign_page_looks_abnormal(page: str) -> bool:
    return "今天签到" not in page and "累签" not in page and "月累签" not in page


def perform_sign(account: Account, credential_source: str) -> SignResult:
    params = {"openId": account.open_id, "sid": account.sid}
    client = HttpClient()

    client.fetch(HOME_PATH, params)
    sign_page = client.fetch(SIGN_PATH, params)

    signed_now = False
    if not is_signed(sign_page):
        action = extract_sign_action(sign_page)
        if not action:
            print("签到结果=未找到签到入口")
            return SignResult(False, credential_source, "no_sign_action_found", "none")
        client.fetch(action)
        signed_now = True

    final_sign_page = client.fetch(SIGN_PATH, params)
    print_summary(final_sign_page)
    if not is_signed(final_sign_page):
        print("签到结果=签到失败")
        return SignResult(False, credential_source, "sign_failed", "none")

    result_value = "signed" if signed_now else "already_signed"
    print(f"签到结果={'签到成功' if signed_now else '今日已签到'}")

    reward_actions = extract_reward_actions(final_sign_page)
    if not reward_actions:
        print("奖励领取=无可领取奖励")
        return SignResult(True, credential_source, result_value, "none")

    for reward_action in reward_actions:
        client.fetch(reward_action)

    reward_check_page = client.fetch(SIGN_PATH, params)
    print_summary(reward_check_page)
    print("奖励领取=已完成")
    return SignResult(True, credential_source, result_value, "done")


def run_sign(account: Account) -> SignResult:
    account, credential_source = resolve_game_account(account)
    if credential_source == "cache" and account.has_login_credentials:
        params = {"openId": account.open_id, "sid": account.sid}
        client = HttpClient()
        sign_page = client.fetch(SIGN_PATH, params)
        if sign_page_looks_abnormal(sign_page):
            account, credential_source = refresh_game_account(account)
    source_labels = {
        "direct": "直接凭证",
        "cache": "缓存",
        "login": "登录",
        "login_refresh": "刷新登录",
    }
    print(f"凭证来源={source_labels.get(credential_source, credential_source)}")
    print(f"牧场首页链接={BASE_URL}{HOME_PATH}?ver=0&sid={account.sid}&openId={account.open_id}")
    return perform_sign(account, credential_source)
