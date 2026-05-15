import re
from dataclasses import dataclass, field
from html import unescape

from ygmc.config import Account, HOME_PATH
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account

SUNSHINE_PATH = "/ygmc/aid/index.go"
DIG_INDEX_PATH = "/ygmc/dig/index.go"
SYNTHESIS_DETAIL_PATH = "/ygmc/synthesis/synthesisDetail.go"


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
    active_actions: list[str] = field(default_factory=list)


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


def _task_remaining(tasks: list[SunshineTask], keyword: str, target_count: int) -> int:
    for task in tasks:
        if keyword not in task.description:
            continue
        if task.completed:
            return 0
        if "/" not in task.progress:
            return target_count
        current, target = task.progress.split("/", 1)
        try:
            return max(0, int(target) - int(current))
        except ValueError:
            return target_count
    return 0


def _extract_form_action(page: str, action_keyword: str) -> str | None:
    match = re.search(
        rf"<form\s+[^>]*action=['\"]([^'\"]*{re.escape(action_keyword)}[^'\"]*)['\"]",
        page,
        re.I,
    )
    if not match:
        return None
    return unescape(match.group(1))


def _extract_link_by_text(page: str, keyword: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        if keyword in plain:
            return unescape(href)
    return None


def _extract_normal_dig_link(page: str) -> str | None:
    for fragment in re.split(r"<br\s*/?>", page, flags=re.I):
        if "普通藏宝图" not in fragment:
            continue
        link = _extract_link_by_text(fragment, "挖宝")
        if link:
            return link
    return None


def _extract_dig_node_link(page: str) -> str | None:
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        plain = _clean_text(text)
        href = unescape(href)
        if "dig.go" in href and plain not in ("返回前页", "返回挖宝首页"):
            return href
    return None


def _run_dig_task(client: HttpClient, params: dict[str, str], times: int) -> int:
    done = 0
    for _ in range(times):
        dig_index_page = client.fetch(DIG_INDEX_PATH, {**params, "ver": "null"})
        map_link = _extract_link_by_text(dig_index_page, "天圣雪山")
        if not map_link:
            break
        map_page = client.fetch(map_link)
        dig_link = _extract_normal_dig_link(map_page)
        if not dig_link:
            break
        node_page = client.fetch(dig_link)
        node_link = _extract_dig_node_link(node_page)
        if not node_link:
            break
        client.fetch(node_link)
        done += 1
    return done


def _run_synthesis_task(client: HttpClient, params: dict[str, str]) -> bool:
    detail_page = client.fetch(SYNTHESIS_DETAIL_PATH, {**params, "id": "66", "type": "1"})
    action = _extract_form_action(detail_page, "synthesis.go")
    if not action:
        return False
    client.fetch(action, data={"id": "66", "count": "3"})
    return True


def _run_active_tasks(client: HttpClient, params: dict[str, str], tasks: list[SunshineTask]) -> list[str]:
    actions: list[str] = []

    dig_remaining = _task_remaining(tasks, "挖宝", 2)
    if dig_remaining > 0:
        dig_done = _run_dig_task(client, params, min(dig_remaining, 2))
        actions.append(f"挖宝={dig_done}次")

    synthesis_remaining = _task_remaining(tasks, "制造屋合成", 3)
    if synthesis_remaining > 0:
        synthesis_done = _run_synthesis_task(client, params)
        actions.append("制造屋合成=3次" if synthesis_done else "制造屋合成=失败")

    return actions


def run_sunshine(account: Account, summary_only: bool = False) -> SunshineResult:
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
    active_actions = _run_active_tasks(client, params, tasks)
    if active_actions:
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

    if summary_only:
        if active_actions:
            print(f"活跃操作={','.join(active_actions)}")
        print(f"今日阳光值={total_points}点")
        return SunshineResult(
            ok=vip_reward_status != "failed",
            credential_source=credential_source,
            total_points=total_points,
            tasks=tasks,
            vip_reward_status=vip_reward_status,
            active_actions=active_actions,
        )

    if active_actions:
        print(f"活跃操作={','.join(active_actions)}")
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
        active_actions=active_actions,
    )
