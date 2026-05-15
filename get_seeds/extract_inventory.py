# extract_inventory.py
import csv
import json
import re
import time
from pathlib import Path

import requests


CACHE_PATH = Path(__file__).resolve().parent.parent / ".ygmc_cache.json"
CACHE_KEY = "shwaige"

OUTPUT_FILE = "inventory_result.csv"
STORE_URL = "http://mc.pinpinhu.com/ygmc/store/index.go"
SUBTYPE_LABELS = {
    0: "作物",
    1: "鲜花",
    2: "稀有",
    3: "变异",
    4: "太空",
    5: "情侣",
    6: "深海",
    7: "奇珍",
    8: "典藏",
    9: "国粹",
    10: "名著",
    11: "精华",
}


def _load_credentials() -> tuple[str, str]:
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    entry = data[CACHE_KEY]
    return entry["open_id"], entry["sid"]


OPEN_ID, SID = _load_credentials()


def clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    text = (
        text.replace("&middot;", "·")
        .replace("&nbsp;", " ")
        .replace("\r", "")
        .replace("\n", "")
    )
    return re.sub(r"\s+", " ", text).strip()


def fetch_store_page(session: requests.Session, sub_type: int, page_no: int) -> str:
    params = {
        "openId": OPEN_ID,
        "sid": SID,
        "type": "1",
        "subType": str(sub_type),
        "pageNo": str(page_no),
    }
    resp = session.get(STORE_URL, params=params, timeout=20)
    resp.raise_for_status()

    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "ascii"}:
        resp.encoding = resp.apparent_encoding or "utf-8"

    return resp.text


def extract_total_pages(html: str) -> int:
    match = re.search(r"第\d+/(\d+)页", html)
    if not match:
        return 1
    return int(match.group(1))


def extract_inventory_items(html: str, category: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for fragment in re.split(r"<br\s*/?>", html, flags=re.I):
        if "goodsInfo.go" not in fragment:
            continue

        match = re.search(
            r"goodsInfo\.go[^'\"]*id=([^'\"&]+)[^'\"]*['\"][^>]*>(.*?)</a>\s*×\s*(\d+)",
            fragment,
            re.I | re.S,
        )
        if not match:
            continue

        item_id, raw_name, quantity = match.groups()
        can_make_sample = "makeSampleIndex.go" in fragment
        items.append(
            {
                "作物ID": item_id.strip(),
                "作物名称": clean_text(raw_name),
                "分类": category,
                "已有数量": quantity.strip(),
                "是否制标": "否" if can_make_sample else "是",
            }
        )
    return items


def merge_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, object]] = {}
    for item in items:
        key = item["作物名称"]
        current = merged.setdefault(
            key,
            {
                "作物ID": item["作物ID"],
                "作物名称": item["作物名称"],
                "分类": item["分类"],
                "已有数量": 0,
                "是否制标": "是",
            },
        )
        current["已有数量"] = int(current["已有数量"]) + int(item["已有数量"])
        if item["分类"] not in str(current["分类"]).split("、"):
            current["分类"] = f"{current['分类']}、{item['分类']}"
        if item["是否制标"] == "否":
            current["是否制标"] = "否"

    return [
        {
            "作物ID": str(item["作物ID"]),
            "作物名称": str(item["作物名称"]),
            "分类": str(item["分类"]),
            "已有数量": str(item["已有数量"]),
            "是否制标": str(item["是否制标"]),
        }
        for item in merged.values()
    ]


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            )
        }
    )

    items: list[dict[str, str]] = []
    for sub_type, category in SUBTYPE_LABELS.items():
        first_page = fetch_store_page(session, sub_type, 1)
        total_pages = extract_total_pages(first_page)
        page_items = extract_inventory_items(first_page, category)
        items.extend(page_items)
        print(f"正在抓取{category}第 1/{total_pages} 页，提取 {len(page_items)} 条")

        for page_no in range(2, total_pages + 1):
            page = fetch_store_page(session, sub_type, page_no)
            page_items = extract_inventory_items(page, category)
            items.extend(page_items)
            print(f"正在抓取{category}第 {page_no}/{total_pages} 页，提取 {len(page_items)} 条")
            time.sleep(0.1)

    results = merge_items(items)
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["作物ID", "作物名称", "分类", "已有数量", "是否制标"])
        writer.writeheader()
        writer.writerows(results)

    print(f"完成，共 {len(results)} 种作物，结果已保存到：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
