import os

from ygmc.config import Account


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"缺少环境变量：{name}")
    return value


def load_account_from_env() -> Account:
    label = os.environ.get("YGMC_LABEL", "env_account").strip() or "env_account"
    open_id = os.environ.get("YGMC_OPEN_ID", "").strip()
    sid = os.environ.get("YGMC_SID", "").strip()
    login_account = os.environ.get("YGMC_LOGIN_ACCOUNT", "").strip()
    login_password = os.environ.get("YGMC_LOGIN_PASSWORD", "").strip()

    if open_id and sid:
        return Account(label=label, open_id=open_id, sid=sid)
    if login_account and login_password:
        return Account(label=label, login_account=login_account, login_password=login_password)
    raise ValueError(
        "缺少凭证，请设置 YGMC_OPEN_ID/YGMC_SID 或 YGMC_LOGIN_ACCOUNT/YGMC_LOGIN_PASSWORD"
    )


def parse_accounts_file(path: str) -> list[Account]:
    accounts: list[Account] = []
    with open(path, "r", encoding="utf-8") as f:
        for index, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 2:
                open_id, sid = parts
                label = f"account_{index}"
                accounts.append(Account(label=label, open_id=open_id, sid=sid))
            elif len(parts) == 3:
                label, open_id, sid = parts
                accounts.append(Account(label=label, open_id=open_id, sid=sid))
            elif len(parts) == 4:
                label, login_account, login_password, mode = parts
                if mode != "login":
                    raise ValueError(f"第 {index} 行格式错误：mode 必须是 login")
                accounts.append(
                    Account(label=label, login_account=login_account, login_password=login_password)
                )
            elif len(parts) == 6:
                label_prefix, login_prefix, start, end, login_password, mode = parts
                if mode != "login_range":
                    raise ValueError(f"第 {index} 行格式错误：mode 必须是 login_range")
                try:
                    start_num = int(start)
                    end_num = int(end)
                except ValueError as exc:
                    raise ValueError(f"第 {index} 行格式错误：start 和 end 必须是整数") from exc
                if start_num > end_num:
                    raise ValueError(f"第 {index} 行格式错误：start 不能大于 end")
                for num in range(start_num, end_num + 1):
                    accounts.append(
                        Account(
                            label=f"{label_prefix}{num}",
                            login_account=f"{login_prefix}{num}",
                            login_password=login_password,
                        )
                    )
            else:
                raise ValueError(f"第 {index} 行格式错误：{raw_line.rstrip()}")
    return accounts
