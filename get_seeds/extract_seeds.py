# extract_seeds.py
import re
import requests

BASE = "http://mc.pinpinhu.com/ygmc/store/index.go"

OPEN_ID = "fb881448c456f31cb8c2f854762a6aff"
SID = "8b9a61d547b352ce042d339dd550b5b293881c16"

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

    for page_no in range(1, 13):
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