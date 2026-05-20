from __future__ import annotations

# 根据已有稀有标本排除已有种子 并输出没有制标的已有稀有种子

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

import requests

EXCLUDED_SEED_NAMES = {
  "果石榴",
  "泽米铁",
  "属金兰",
  "麦红花",
  "金红花",
  "红赤云",
  "白晨蓝",
  "独叶草",
  "断肠草",
  "风信子",
  "灵芝",
  "依米花",
  "雪绒花",
  "黄金珊瑚",
  "彼岸花",
  "野山参",
  "亮红仙人指",
  "黄玫瑰",
  "蓝玫瑰",
  "粉玫瑰",
  "火焰花",
  "何首乌",
  "昙花",
  "狗尾草",
  "白花藿香蓟",
  "圆孔方木",
  "庆赏艳梅",
  "聚合草",
  "黑种花",
  "千里光",
  "宿根亚麻",
  "圣诞铃铛",
  "圣诞花塔",
  "圣诞平安果",
  "圣诞雪人",
  "孔雀竹芋",
  "聚福草莓",
  "满福金葫",
  "女神之泪"
}


STORE_URL = "http://mc.pinpinhu.com/ygmc/store/index.go"
GOODS_INFO_URL = "http://mc.pinpinhu.com/ygmc/store/goodsInfo.go"
OPEN_ID = "fb881448c456f31cb8c2f854762a6aff"
SID = "5058674ebbc68ca695a9364750334f96e4ee5cd3"
TIMEOUT = 20
OUTPUT_FILE = Path(__file__).with_name("query_rare_seed_inventory.csv")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class SeedSummary:
    seed_id: str
    name: str


def normalize_response_text(response: requests.Response) -> str:
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "ascii"}:
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    text = html.unescape(text)
    text = text.replace("\r", "").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def fetch_store_page(session: requests.Session, page_no: int) -> str:
    response = session.get(
        STORE_URL,
        params={
            "openId": OPEN_ID,
            "sid": SID,
            "type": "0",
            "subType": "2",
            "pageNo": str(page_no),
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return normalize_response_text(response)


def fetch_goods_info(session: requests.Session, seed_id: str) -> str:
    response = session.get(
        GOODS_INFO_URL,
        params={
            "openId": OPEN_ID,
            "sid": SID,
            "id": seed_id,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return normalize_response_text(response)


def parse_total_pages(page_html: str) -> int:
    match = re.search(r"第\s*\d+\s*/\s*(\d+)页", page_html)
    if not match:
        return 1
    return max(1, int(match.group(1)))


def parse_owned_seeds(page_html: str) -> list[SeedSummary]:
    results: list[SeedSummary] = []
    seen: set[str] = set()
    item_pattern = re.compile(
        r"goodsInfo\.go[^\"'>]*id=([^\"'&>]+)[^\"'>]*[\"'][^>]*>(.*?)</a>\s*×\s*(\d+)",
        re.I | re.S,
    )

    for seed_id, raw_name, quantity in item_pattern.findall(page_html):
        seed_id = seed_id.strip()
        if not seed_id or seed_id in seen:
            continue
        if not quantity.strip() or quantity.strip() == "0":
            continue
        seen.add(seed_id)
        name = clean_text(raw_name)
        if not name:
            name = seed_id
        results.append(SeedSummary(seed_id=seed_id, name=name))

    return results


def parse_mature_time(detail_html: str) -> str:
    text = clean_text(detail_html)
    for pattern in (
        r"初次成熟[:：]\s*([0-9]+(?:\.[0-9]+)?\s*小时)",
        r"成熟时间[:：]\s*([0-9]+(?:\.[0-9]+)?\s*小时)",
        r"初次成熟[:：]\s*([^\s，。,；;]+)",
        r"成熟时间[:：]\s*([^\s，。,；;]+)",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return "未解析到成熟时间"


def simplify_seed_name(name: str) -> str:
    return name.replace("[种子]", "").strip()


def simplify_mature_time(mature_time: str) -> str:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", mature_time)
    if match:
        return match.group(1)
    return mature_time


def build_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def main() -> int:
    session = build_session()
    owned_seeds: dict[str, SeedSummary] = {}
    first_page_ok = False
    total_pages = 1

    try:
        first_page = fetch_store_page(session, 1)
    except Exception as exc:
        print(f"请求第 1 页失败：{exc}")
    else:
        first_page_ok = True
        total_pages = parse_total_pages(first_page)
        for seed in parse_owned_seeds(first_page):
            owned_seeds[seed.seed_id] = seed

    if not first_page_ok:
        return 1

    for page_no in range(2, total_pages + 1):
        try:
            page_html = fetch_store_page(session, page_no)
        except Exception as exc:
            print(f"请求第 {page_no} 页失败：{exc}")
            continue
        for seed in parse_owned_seeds(page_html):
            owned_seeds[seed.seed_id] = seed

    if not owned_seeds:
        print("未发现已有稀有种子")
        return 0

    rows: list[dict[str, str]] = []
    for seed in owned_seeds.values():
        seed_name = simplify_seed_name(seed.name)
        if seed_name in EXCLUDED_SEED_NAMES:
            continue
        try:
            detail_html = fetch_goods_info(session, seed.seed_id)
        except Exception as exc:
            print(f"{seed_name} 查询失败：{exc}")
            continue
        mature_time = parse_mature_time(detail_html)
        rows.append(
            {
                "未制标已有种子": seed_name,
                "成熟时间": simplify_mature_time(mature_time),
            }
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["未制标已有种子", "成熟时间"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"已输出到：{OUTPUT_FILE.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
