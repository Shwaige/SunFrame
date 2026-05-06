import json
from pathlib import Path

from ygmc.config import Account, BASE_URL, CACHE_PATH, HOME_PATH


def load_cache(path: Path = CACHE_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, dict[str, str]], path: Path = CACHE_PATH) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_cached_game_account(account: Account) -> Account | None:
    cache = load_cache()
    record = cache.get(account.cache_key)
    if not record:
        return None
    open_id = record.get("open_id", "").strip()
    sid = record.get("sid", "").strip()
    if not open_id or not sid:
        return None
    return Account(
        label=account.label,
        open_id=open_id,
        sid=sid,
        login_account=account.login_account,
        login_password=account.login_password,
    )


def update_cached_game_account(account: Account) -> None:
    cache = load_cache()
    cache[account.cache_key] = {
        "open_id": account.open_id,
        "sid": account.sid,
        "home_url": f"{BASE_URL}{HOME_PATH}?ver=0&sid={account.sid}&openId={account.open_id}",
    }
    save_cache(cache)
