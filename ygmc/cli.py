import sys

from ygmc.accounts import load_account_from_env, parse_accounts_file
from ygmc.activity import run_activity
from ygmc.cache import get_cached_game_account
from ygmc.config import BASE_URL, HOME_PATH
from ygmc.farm_status import run_farm_status
from ygmc.friends_ops import run_friends_ops
from ygmc.self_ops import run_self_ops
from ygmc.sign import run_sign
from ygmc.sunshine import run_sunshine


def print_usage() -> None:
    print("用法：", file=sys.stderr)
    print("  python3 -m ygmc.cli sign [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli activity [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli sunshine [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli daily [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli daily-self [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli self-op [accounts.txt]", file=sys.stderr)
    print("  python3 -m ygmc.cli status", file=sys.stderr)
    print("  python3 -m ygmc.cli friends-op", file=sys.stderr)
    print("  python3 ygmc_sign.py [accounts.txt]", file=sys.stderr)
    print("环境变量模式：", file=sys.stderr)
    print("  YGMC_OPEN_ID + YGMC_SID", file=sys.stderr)
    print("  或 YGMC_LOGIN_ACCOUNT + YGMC_LOGIN_PASSWORD", file=sys.stderr)


def handle_sign(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                result = run_sign(account)
                summary.append(
                    (account.label, "ok" if result.ok else "fail", result.credential_source, result.result)
                )
                if result.reward != "none":
                    summary[-1] = (
                        account.label,
                        "ok" if result.ok else "fail",
                        result.credential_source,
                        f"{result.result},reward={result.reward}",
                    )
            except Exception as exc:
                print(f"result=错误 {exc}")
                summary.append((account.label, "fail", "error", str(exc)))
        print("== summary ==")
        for label, status, source, detail in summary:
            print(f"{label}\t{status}\t{source}\t{detail}")
        failures = sum(1 for _, status, _, _ in summary if status != "ok")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if run_sign(account).ok else 1


def run_daily_for_account(account) -> bool:
    print("========== 签到 ==========")
    sign_result = run_sign(account)
    print("========== 活动 ==========")
    activity_result = run_activity(account)
    print("========== 我的农场/牧场 ==========")
    self_result = run_self_ops(account)
    print("========== 好友农场/牧场 ==========")
    friends_result = run_friends_ops(account)
    return sign_result.ok and activity_result.ok and self_result.ok and friends_result.ok


def run_daily_self_for_account(account) -> bool:
    print("========== 签到 ==========")
    sign_result = run_sign(account)
    print("========== 活动 ==========")
    activity_result = run_activity(account)
    print("========== 我的农场/牧场 ==========")
    self_result = run_self_ops(account)
    return sign_result.ok and activity_result.ok and self_result.ok


def print_final_home_link(account) -> None:
    final_account = get_cached_game_account(account) if account.has_login_credentials else account
    if not final_account or not final_account.has_game_credentials:
        return
    print("========== 完成 ==========")
    print(f"农场链接：{BASE_URL}{HOME_PATH}?ver=0&sid={final_account.sid}&openId={final_account.open_id}")


def handle_self_ops(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                result = run_self_ops(account)
                summary.append((account.label, "成功" if result.ok else "失败", f"收获明细={len(result.harvest_details)}"))
            except Exception as exc:
                print(f"结果=错误 {exc}")
                summary.append((account.label, "失败", str(exc)))
        print("== 汇总 ==")
        for label, status, detail in summary:
            print(f"{label}\t{status}\t{detail}")
        failures = sum(1 for _, status, _ in summary if status != "成功")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if run_self_ops(account).ok else 1


def handle_sunshine(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                result = run_sunshine(account)
                summary.append((account.label, "成功" if result.ok else "失败", f"阳光值={result.total_points}"))
            except Exception as exc:
                print(f"结果=错误 {exc}")
                summary.append((account.label, "失败", str(exc)))
        print("== 汇总 ==")
        for label, status, detail in summary:
            print(f"{label}\t{status}\t{detail}")
        failures = sum(1 for _, status, _ in summary if status != "成功")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if run_sunshine(account).ok else 1


def handle_activity(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                result = run_activity(account)
                detail = f"新人红包={result.newcomer_red_packet_status}"
                summary.append((account.label, "成功" if result.ok else "失败", detail))
            except Exception as exc:
                print(f"结果=错误 {exc}")
                summary.append((account.label, "失败", str(exc)))
        print("== 汇总 ==")
        for label, status, detail in summary:
            print(f"{label}\t{status}\t{detail}")
        failures = sum(1 for _, status, _ in summary if status != "成功")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if run_activity(account).ok else 1


def handle_daily(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                ok = run_daily_for_account(account)
                print_final_home_link(account)
                summary.append((account.label, "成功" if ok else "失败", "daily"))
            except Exception as exc:
                print(f"结果=错误 {exc}")
                summary.append((account.label, "失败", str(exc)))
        print("== 汇总 ==")
        for label, status, detail in summary:
            print(f"{label}\t{status}\t{detail}")
        failures = sum(1 for _, status, _ in summary if status != "成功")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    ok = run_daily_for_account(account)
    print_final_home_link(account)
    return 0 if ok else 1


def handle_daily_self(argv: list[str]) -> int:
    if len(argv) > 1:
        print_usage()
        return 2

    if len(argv) == 1:
        try:
            accounts = parse_accounts_file(argv[0])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        summary: list[tuple[str, str, str]] = []
        for account in accounts:
            print(f"== {account.label} ==")
            try:
                ok = run_daily_self_for_account(account)
                print_final_home_link(account)
                summary.append((account.label, "成功" if ok else "失败", "daily-self"))
            except Exception as exc:
                print(f"结果=错误 {exc}")
                summary.append((account.label, "失败", str(exc)))
        print("== 汇总 ==")
        for label, status, detail in summary:
            print(f"{label}\t{status}\t{detail}")
        failures = sum(1 for _, status, _ in summary if status != "成功")
        return 1 if failures else 0

    try:
        account = load_account_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    ok = run_daily_self_for_account(account)
    print_final_home_link(account)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print_usage()
        return 2

    command = argv.pop(0)
    if command == "sign":
        return handle_sign(argv)
    if command == "activity":
        return handle_activity(argv)
    if command == "sunshine":
        return handle_sunshine(argv)
    if command == "daily":
        return handle_daily(argv)
    if command == "daily-self":
        return handle_daily_self(argv)
    if command == "self-op":
        return handle_self_ops(argv)
    if command == "status":
        if argv:
            print_usage()
            return 2
        try:
            account = load_account_from_env()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0 if run_farm_status(account).ok else 1
    if command == "friends-op":
        if argv:
            print_usage()
            return 2
        try:
            account = load_account_from_env()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0 if run_friends_ops(account).ok else 1

    print(f"未知命令：{command}", file=sys.stderr)
    print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
