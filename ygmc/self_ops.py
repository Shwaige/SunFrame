import html
import re
from dataclasses import dataclass, field

from ygmc.config import Account, HOME_PATH
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account


@dataclass
class SelfActionResult:
    area: str
    action: str
    ok: bool
    detail: list[str] = field(default_factory=list)


@dataclass
class SelfTarget:
    name: str
    detail_link: str
    direct_links: list[str] = field(default_factory=list)


@dataclass
class SelfOpsResult:
    ok: bool
    credential_source: str
    actions: list[SelfActionResult] = field(default_factory=list)
    harvest_details: list[str] = field(default_factory=list)
    errors: int = 0
    skipped: int = 0


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return html.unescape(text).replace("\r", "").strip()


def _page_lines(page: str) -> list[str]:
    page = re.sub(r"<br\s*/?>", "\n", page, flags=re.I)
    page = re.sub(r"</p>|</div>|</li>", "\n", page, flags=re.I)
    text = _clean_text(page)
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def _result_details(page: str) -> list[str]:
    keywords = [
        "获得",
        "收获",
        "操作",
        "铲除",
        "铲地",
        "清除",
        "成功",
        "失败",
        "没有",
        "暂无",
        "成熟",
        "产量",
        "经验",
        "金币",
        "银币",
        "果实",
        "产品",
        "背包",
        "仓库",
    ]
    skip_markers = ["牧场>", "返回", "刷新", "首页", "查看详情"]
    details = [
        line
        for line in _page_lines(page)
        if any(keyword in line for keyword in keywords)
        and not re.fullmatch(r"\[[^]]+\]", line)
        and not any(marker in line for marker in skip_markers)
    ]
    return details[:20]


def _extract_action_links(page: str, labels: set[str], path_markers: tuple[str, ...]) -> dict[str, str]:
    links: dict[str, str] = {}
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", page, re.I | re.S):
        label = _clean_text(text)
        href = html.unescape(href)
        if label in labels and any(marker in href for marker in path_markers):
            links[label] = href
    return links


def _extract_links(fragment: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for href, text in re.findall(r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", fragment, re.I | re.S):
        links.append((html.unescape(href), _clean_text(text)))
    return links


def _link_matches(label: str, labels: set[str]) -> bool:
    compact = label.strip("[]")
    return label in labels or compact in labels


def _extract_targets(
    page: str,
    detail_marker: str,
    id_name: str,
    action_labels: set[str],
) -> list[SelfTarget]:
    targets: list[SelfTarget] = []
    for fragment in re.split(r"<br\s*/?>", page, flags=re.I):
        if detail_marker not in fragment or id_name not in fragment:
            continue
        links = _extract_links(fragment)
        if not any(_link_matches(label, action_labels) for _, label in links):
            continue

        detail_link = ""
        direct_links: list[str] = []
        target_name = ""
        for href, label in links:
            if detail_marker in href and id_name in href and not detail_link:
                detail_link = href
                target_name = label
            elif _link_matches(label, action_labels):
                direct_links.append(href)

        if detail_link:
            name = target_name or _clean_text(fragment)
            targets.append(SelfTarget(name=name, detail_link=detail_link, direct_links=direct_links))
    return targets


def _farm_targets(page: str, action: str) -> list[SelfTarget]:
    labels = {
        "操作": {"浇水", "除草", "捉虫", "[浇水]", "[除草]", "[捉虫]"},
        "收获": {"收获", "[收获]"},
        "铲除": {"铲除", "铲地", "[铲除]", "[铲地]"},
    }
    return _extract_targets(page, "fieldDetail.go", "fieldId", labels[action])


def _ranch_targets(page: str, action: str) -> list[SelfTarget]:
    labels = {
        "操作": { "喂水", "清理",  "治疗", "帮助",  "[喂水]", "[清理]", "[治疗]", "[帮助]"},
        "收获": {"收获", "生产", "捉取", "[收获]", "[生产]", "[捉取]"},
    }
    return _extract_targets(page, "animalDetail.go", "siteId", labels[action])


def _fetch_self_pages(account: Account) -> tuple[HttpClient, dict[str, str], str, str]:
    params = {"openId": account.open_id, "sid": account.sid}
    client = HttpClient()
    farm_page = client.fetch(HOME_PATH, params)
    ranch_page = client.fetch(HOME_PATH, {**params, "indexType": "1"})
    return client, params, farm_page, ranch_page


def _self_state_looks_abnormal(farm_page: str, ranch_page: str) -> bool:
    combined_page = f"{farm_page}\n{ranch_page}"
    combined_text = _clean_text(combined_page)
    if "login.action" in combined_page or "loginValidate.action" in combined_page:
        return True
    has_game_content = any(marker in combined_page for marker in ("fieldDetail.go", "animalDetail.go"))
    has_game_text = "农场" in combined_text or "牧场" in combined_text
    return "登录" in combined_text and not has_game_content and not has_game_text


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _fetch_with_retry(client: HttpClient, link: str) -> str:
    try:
        return client.fetch(link)
    except TimeoutError:
        return client.fetch(link)


def _action_failed(details: list[str]) -> bool:
    failure_markers = ["无", "没有", "暂无", "失败", "不能", "不可", "不足"]
    return any(any(marker in detail for marker in failure_markers) for detail in details)


def _extract_single_action_links(page: str, action_labels: set[str]) -> list[str]:
    links: list[str] = []
    for href, label in _extract_links(page):
        if _link_matches(label, action_labels):
            links.append(href)
    return links


def _single_action_labels(area: str, action: str) -> set[str]:
    if area == "农场":
        return {
            "操作": {"浇水", "除草", "捉虫", "[浇水]", "[除草]", "[捉虫]"},
            "收获": {"收获", "[收获]"},
            "铲除": {"铲除", "铲地", "[铲除]", "[铲地]"},
        }[action]
    return {
        "操作": {"喂养", "喂水", "清理", "清洁", "治疗", "帮助", "[喂养]", "[喂水]", "[清理]", "[清洁]", "[治疗]", "[帮助]"},
        "收获": {"收获", "生产", "捉取", "[收获]", "[生产]", "[捉取]"},
    }[action]


def _run_single_actions(client: HttpClient, area: str, action: str, targets: list[SelfTarget]) -> list[str]:
    labels = _single_action_labels(area, action)
    details: list[str] = []
    for target in targets:
        links = list(target.direct_links)
        if not links:
            detail_page = _fetch_with_retry(client, target.detail_link)
            links = _extract_single_action_links(detail_page, labels)
        if not links:
            details.append(f"{target.name}=未找到单个{action}入口")
            continue
        for link in links:
            page = _fetch_with_retry(client, link)
            action_details = _result_details(page)
            if action_details:
                details.extend(f"{target.name}|{detail}" for detail in action_details)
            else:
                details.append(f"{target.name}=单个{action}完成")
    return details


def _run_action(
    client: HttpClient,
    area: str,
    action: str,
    link: str,
    targets: list[SelfTarget],
) -> SelfActionResult:
    page = _fetch_with_retry(client, link)
    details = _result_details(page)
    if not details or _action_failed(details):
        single_details = _run_single_actions(client, area, action, targets)
        if single_details:
            details = single_details
        elif not details:
            details = ["无返回明细"]
    return SelfActionResult(area=area, action=action, ok=True, detail=details)


def _run_planned_action(
    client: HttpClient,
    area: str,
    action: str,
    link: str | None,
    targets: list[SelfTarget],
) -> tuple[SelfActionResult, int]:
    if not targets:
        detail = f"未显示可{action}项，跳过"
        return SelfActionResult(area=area, action=action, ok=True, detail=[detail]), 0
    if not link:
        try:
            details = _run_single_actions(client, area, action, targets)
            if not details:
                return SelfActionResult(area=area, action=action, ok=False, detail=["未找到入口"]), 1
            return SelfActionResult(area=area, action=action, ok=True, detail=details), 0
        except Exception as exc:
            detail = _error_text(exc)
            print(f"{area}{action}=失败|错误={detail}")
            return SelfActionResult(area=area, action=action, ok=False, detail=[detail]), 1
    try:
        return _run_action(client, area, action, link, targets), 0
    except Exception as exc:
        detail = _error_text(exc)
        print(f"{area}{action}=失败|错误={detail}")
        return SelfActionResult(area=area, action=action, ok=False, detail=[detail]), 1


def run_self_ops(account: Account) -> SelfOpsResult:
    game_account, credential_source = resolve_game_account(account)
    client, params, farm_page, ranch_page = _fetch_self_pages(game_account)
    if credential_source == "cache" and account.has_login_credentials:
        if _self_state_looks_abnormal(farm_page, ranch_page):
            try:
                game_account, credential_source = refresh_game_account(account)
                client, params, farm_page, ranch_page = _fetch_self_pages(game_account)
            except Exception as exc:
                print(f"重新登录失败，继续使用缓存|错误={_error_text(exc)}")

    actions: list[SelfActionResult] = []
    errors = 0

    farm_links = _extract_action_links(farm_page, {"操作", "收获", "铲除"}, ("oneKeyFarm", "oneKeyUproot"))
    for action in ("操作", "收获"):
        result, action_errors = _run_planned_action(
            client,
            "农场",
            action,
            farm_links.get(action),
            _farm_targets(farm_page, action),
        )
        actions.append(result)
        errors += action_errors

    farm_page = client.fetch(HOME_PATH, params)
    farm_links = _extract_action_links(farm_page, {"铲除"}, ("oneKeyUproot",))
    result, action_errors = _run_planned_action(
        client,
        "农场",
        "铲除",
        farm_links.get("铲除"),
        _farm_targets(farm_page, "铲除"),
    )
    actions.append(result)
    errors += action_errors

    ranch_links = _extract_action_links(ranch_page, {"操作", "收获"}, ("oneKeyRanch",))
    for action in ("操作", "收获"):
        result, action_errors = _run_planned_action(
            client,
            "畜牧场",
            action,
            ranch_links.get(action),
            _ranch_targets(ranch_page, action),
        )
        actions.append(result)
        errors += action_errors

    harvest_details = [
        detail
        for result in actions
        if result.action == "收获"
        for detail in result.detail
        if not detail.startswith("未显示")
    ]
    skipped = sum(1 for result in actions if result.detail and result.detail[0].startswith("未显示"))
    done = sum(1 for result in actions if result.ok and not (result.detail and result.detail[0].startswith("未显示")))
    if done == 0 and errors == 0:
        print("自己操作=未进行实际操作")
    else:
        print(f"自己操作数量={done}")
        if skipped:
            print(f"自己操作跳过数量={skipped}")
        print(f"自己操作失败数量={errors}")
    return SelfOpsResult(
        ok=errors == 0,
        credential_source=credential_source,
        actions=actions,
        harvest_details=harvest_details,
        errors=errors,
        skipped=skipped,
    )
