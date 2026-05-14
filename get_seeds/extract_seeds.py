# extract_seeds.py
import json
import re
from pathlib import Path

import requests

BASE = "http://mc.pinpinhu.com/ygmc/store/index.go"

CACHE_PATH = Path(__file__).resolve().parent.parent / ".ygmc_cache.json"
CACHE_KEY = "shwaige"


def _load_credentials() -> tuple[str, str]:
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    entry = data[CACHE_KEY]
    return entry["open_id"], entry["sid"]


OPEN_ID, SID = _load_credentials()

OUTPUT_FILE = "seeds.txt"


def fetch_page(page_no: int) -> str:
    params = {
        "openId": OPEN_ID,
        "sid": SID,
        "pageNo": page_no,
    }

    resp = requests.get(BASE, params=params, timeout=20)
    resp.raise_for_status()

    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "ascii"}:
        resp.encoding = resp.apparent_encoding or "utf-8"

    return resp.text


def extract_seeds(html: str):
    """
    匹配这种结构：
    id=zzaqws001'>[种子]安全卫士
    """
    pattern = r"id=([^'&]+)'>\[种子\]([^<]+)"
    return re.findall(pattern, html)


def main():
    results = []

    for page_no in range(1, 30):
        print(f"正在抓取第 {page_no} 页...")

        html = fetch_page(page_no)
        seeds = extract_seeds(html)

        for seed_id, crop_name in seeds:
            results.append((seed_id.strip(), crop_name.strip()))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for seed_id, crop_name in results:
            f.write(f"{seed_id}\t{crop_name}\n")

    print(f"完成，共提取 {len(results)} 条，已写入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()