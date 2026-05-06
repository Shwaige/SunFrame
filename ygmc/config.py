from dataclasses import dataclass
from pathlib import Path


BASE_URL = "http://mc.pinpinhu.com"
HOME_PATH = "/ygmc/home/index.go"
SIGN_PATH = "/ygmc/sign/index.go"
DEFAULT_TIMEOUT = 20
CACHE_PATH = Path(".ygmc_cache.json")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)


@dataclass(frozen=True)
class Account:
    label: str
    open_id: str = ""
    sid: str = ""
    login_account: str = ""
    login_password: str = ""

    @property
    def has_game_credentials(self) -> bool:
        return bool(self.open_id and self.sid)

    @property
    def has_login_credentials(self) -> bool:
        return bool(self.login_account and self.login_password)

    @property
    def cache_key(self) -> str:
        if self.label:
            return self.label
        if self.login_account:
            return self.login_account
        if self.open_id:
            return self.open_id
        return "default"
