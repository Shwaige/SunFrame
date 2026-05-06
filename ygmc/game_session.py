import html
import re
from urllib.parse import urlencode, urljoin

from ygmc.config import Account
from ygmc.http import HttpClient


H5_BASE_URL = "https://h5.pinpinhu.com"
LOGIN_PATH = "https://h5.pinpinhu.com/loginValidate.action"
GAME_INFO_PATH = "https://h5.pinpinhu.com/game/gameInfo.action"
OLD_SERVER_ZONE_ID = "8"


def extract_old_server_redirect(page: str) -> str:
    match = re.search(
        r"href=['\"]([^'\"]*redirectToGame\.action[^'\"]*gameZoneId=8[^'\"]*)['\"]",
        page,
        re.I,
    )
    if not match:
        raise ValueError("未找到老服跳转入口")
    return html.unescape(match.group(1))


def extract_game_credentials(location: str) -> tuple[str, str]:
    sid_match = re.search(r"[?&]sid=([^&]+)", location)
    openid_match = re.search(r"[?&]openId=([^&]+)", location)
    if not sid_match or not openid_match:
        raise ValueError("未能从跳转地址中解析到游戏凭证")
    return openid_match.group(1), sid_match.group(1)


def login_and_resolve_game_account(account: Account) -> Account:
    if not account.has_login_credentials:
        raise ValueError("需要提供登录账号和密码")

    client = HttpClient()
    client.fetch(
        LOGIN_PATH,
        data={
            "account": account.login_account,
            "password": account.login_password,
            "channel": "",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://h5.pinpinhu.com",
            "Referer": "https://h5.pinpinhu.com/login.action",
        },
    )
    uid = client.cookie_value("login_uid")
    sid = client.cookie_value("login_sid")
    if not uid or not sid:
        raise ValueError("登录失败：未获取到 login_uid 或 login_sid")

    game_info_page = client.fetch(
        f"{GAME_INFO_PATH}?{urlencode({'uid': uid, 'sid': sid, 'gameConfigId': OLD_SERVER_ZONE_ID})}"
    )
    redirect_path = extract_old_server_redirect(game_info_page)
    client.fetch(urljoin(H5_BASE_URL, redirect_path))
    final_url = client.last_url
    if not final_url:
        raise ValueError("未获取到最终游戏地址")
    open_id, game_sid = extract_game_credentials(final_url)
    return Account(label=account.label, open_id=open_id, sid=game_sid)
