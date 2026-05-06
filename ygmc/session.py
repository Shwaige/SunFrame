from ygmc.cache import get_cached_game_account, update_cached_game_account
from ygmc.config import Account
from ygmc.game_session import login_and_resolve_game_account


def resolve_game_account(account: Account) -> tuple[Account, str]:
    if account.has_game_credentials:
        return account, "direct"

    if account.has_login_credentials:
        cached_account = get_cached_game_account(account)
        if cached_account:
            return cached_account, "cache"

        resolved = login_and_resolve_game_account(account)
        update_cached_game_account(resolved)
        return resolved, "login"

    raise ValueError("缺少游戏凭证或登录账号密码")


def refresh_game_account(account: Account) -> tuple[Account, str]:
    if not account.has_login_credentials:
        raise ValueError("刷新游戏凭证需要提供登录账号和密码")
    resolved = login_and_resolve_game_account(account)
    update_cached_game_account(resolved)
    return resolved, "login_refresh"
