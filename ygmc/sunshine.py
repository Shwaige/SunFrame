import re
from dataclasses import dataclass, field

from ygmc.config import Account, HOME_PATH
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account

SUNSHINE_PATH = "/ygmc/aid/index.go"


@dataclass
class SunshineTask:
    task_no: str
    description: str
    progress: str
    completed: bool
    reward: str


@dataclass
class SunshineResult:
    ok: bool
    credential_source: str
    total_points: str
    tasks: list[SunshineTask] = field(default_factory=list)
    vip_reward_status: str = ""


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return text.replace("\r", "").replace("\n", "").replace("&nbsp;", " ").strip()


def _parse_tasks(page: str) -> tuple[str, list[SunshineTask]]:
    total_points = ""
    match = re.search(r"今日累计阳光值[:：]\s*(\d+)点", page)
    if match:
        total_points = match.group(1)

    tasks: list[SunshineTask] = []
    pattern = re.compile(
        r"(?:^|\n)\s*(\d+)\.([^(]+?)\((\d+)点\)\.?([\d/]*\.?)\s*(\(已完成\))?\s*(?:<a[^>]*>[^<]*</a>)?\s*<br",
        re.MULTILINE,
    )
    for match in pattern.finditer(page):
        task_no, desc, points, progress, completed_flag = match.groups()
        desc = _clean_text(desc)
        if not desc:
            continue
        progress = progress.strip().rstrip(".")
        completed = completed_flag is not None or (progress and "/" in progress and progress.split("/")[0] == progress.split("/")[1])

        reward_match = re.search(
            r"奖励[:：]\s*(.*?)\s*<br",
            page[match.end():match.end() + 500],
            re.S,
        )
        reward = _clean_text(reward_match.group(1)) if reward_match else ""

        tasks.append(SunshineTask(
            task_no=task_no,
            description=desc,
            progress=progress,
            completed=completed,
            reward=reward,
        ))
    return total_points, tasks


def _extract_vip_link(page: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = re.sub(r"<.*?>", "", text)
        if "VIP一键完成" in plain:
            return href
    return None


def _has_real_action(total_points: str, vip_reward_status: str) -> bool:
    return vip_reward_status != ""


def run_sunshine(account: Account) -> SunshineResult:
    game_account, credential_source = resolve_game_account(account)
    params = {"openId": game_account.open_id, "sid": game_account.sid}
    client = HttpClient()

    page = client.fetch(SUNSHINE_PATH, params)

    if credential_source == "cache" and account.has_login_credentials:
        if "阳光值" not in page:
            game_account, credential_source = refresh_game_account(account)
            params = {"openId": game_account.open_id, "sid": game_account.sid}
            client = HttpClient()
            page = client.fetch(SUNSHINE_PATH, params)

    total_points, tasks = _parse_tasks(page)

    vip_reward_status = ""
    vip_link = _extract_vip_link(page)
    if vip_link:
        try:
            vip_page = client.fetch(vip_link)
            if "已领取" in vip_page or "完成" in vip_page:
                vip_reward_status = "claimed"
            else:
                vip_reward_status = "clicked"
        except Exception:
            vip_reward_status = "failed"

    completed_count = sum(1 for t in tasks if t.completed)
    print(f"今日阳光值={total_points}点")

    exclude_keywords = ["充值", "消费", "转动风车", "刷新稻草人"]
    pending_tasks = [
        t for t in tasks
        if not t.completed and not any(kw in t.description for kw in exclude_keywords)
    ]

    if pending_tasks:
        print(f"未完成任务={len(pending_tasks)}")
        for task in pending_tasks:
            print(f"  {task.task_no}.{task.description}({task.progress}) 奖励:{task.reward}")
    else:
        print("所有任务已完成")

    if vip_reward_status:
        status_text = {"claimed": "已领取", "clicked": "已点击", "failed": "领取失败"}
        print(f"VIP奖励={status_text.get(vip_reward_status, vip_reward_status)}")

    return SunshineResult(
        ok=vip_reward_status != "failed",
        credential_source=credential_source,
        total_points=total_points,
        tasks=tasks,
        vip_reward_status=vip_reward_status,
    )
