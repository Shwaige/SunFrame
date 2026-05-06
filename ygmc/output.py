import html
import re


SUMMARY_PATTERNS = {
    "today_status": r"今天签到[:：]\s*([^<\n]+)",
    "total_days": r"累计签到[:：]\s*([^<\n]+)",
    "month_days": r"本月签到[:：]\s*([^<\n]+)",
    "today_reward": r"今日签到奖励[:：]\s*([^<\n]+)",
}

SUMMARY_LABELS = {
    "today_status": "今日签到状态",
    "total_days": "累计签到",
    "month_days": "本月签到",
    "today_reward": "今日签到奖励",
}


def extract_summary(page: str) -> dict[str, str]:
    summary: dict[str, str] = {}
    for key, pattern in SUMMARY_PATTERNS.items():
        match = re.search(pattern, page)
        if match:
            summary[key] = html.unescape(match.group(1)).strip()
    return summary


def print_summary(page: str) -> None:
    for key, value in extract_summary(page).items():
        print(f"{SUMMARY_LABELS.get(key, key)}={value}")
