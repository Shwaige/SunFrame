import os

from ygmc.cache import get_cached_game_account, update_cached_game_account
from ygmc.config import Account, HOME_PATH
from ygmc.game_session import login_and_resolve_game_account
from ygmc.http import HttpClient


_FORCED_LOGIN_KEYS: set[str] = set()


def force_login_enabled() -> bool:
    return os.environ.get("YGMC_FORCE_LOGIN", "").strip().lower() in ("1", "true", "yes", "on")


def game_account_looks_valid(account: Account) -> bool:
    params = {"openId": account.open_id, "sid": account.sid}
    client = HttpClient()
    page = client.fetch(HOME_PATH, params)
    if "login.action" in client.last_url:
        return False
    if "fieldDetail.go" in page or "animalDetail.go" in page or "今天签到" in page:
        return True
    return "登录" not in page


def resolve_game_account(account: Account) -> tuple[Account, str]:
    if account.has_game_credentials:
        return account, "direct"

    if account.has_login_credentials:
        force_login = force_login_enabled() and account.cache_key not in _FORCED_LOGIN_KEYS
        if not force_login:
            cached_account = get_cached_game_account(account)
            if cached_account:
                if game_account_looks_valid(cached_account):
                    return cached_account, "cache"
                resolved = login_and_resolve_game_account(account)
                update_cached_game_account(resolved)
                return resolved, "login_refresh"

        resolved = login_and_resolve_game_account(account)
        update_cached_game_account(resolved)
        if force_login:
            _FORCED_LOGIN_KEYS.add(account.cache_key)
        return resolved, "login_forced" if force_login else "login"

    raise ValueError("缺少游戏凭证或登录账号密码")


def refresh_game_account(account: Account) -> tuple[Account, str]:
    if not account.has_login_credentials:
        raise ValueError("刷新游戏凭证需要提供登录账号和密码")
    resolved = login_and_resolve_game_account(account)
    update_cached_game_account(resolved)
    return resolved, "login_refresh"
