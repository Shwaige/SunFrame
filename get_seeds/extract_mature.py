# extract_mature.py
import csv
import re
import time
from pathlib import Path

import requests


OPEN_ID ="fb881448c456f31cb8c2f854762a6aff",
SID = "aa39a18548385960a9199a2ea6cf395e939a1e51"

SEEDS_FILE = "seeds.txt"
OUTPUT_FILE = "mature_result.tsv"

BASE_URL = "http://mc.pinpinhu.com/ygmc/store/goodsInfo.go"


def read_seeds(path: str):
    seeds = []

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            print(f"跳过格式异常行：{line}")
            continue

        seed_id = parts[0].strip()
        crop_name = parts[1].strip()
        seeds.append((seed_id, crop_name))

    return seeds


def extract_mature_time(html: str) -> str:
    # 匹配：初次成熟：90小时 / 初次成熟：0.33小时，只保留数字
    match = re.search(r"初次成熟[:：]\s*([0-9]+(?:\.[0-9]+)?)\s*小时", html)
    if match:
        return match.group(1).strip()

    # 兜底：只要初次成熟后面有整数或小数就提取
    match = re.search(r"初次成熟[:：]\s*([0-9]+(?:\.[0-9]+)?)", html)
    if match:
        return match.group(1).strip()

    return ""


def extract_quantity(html: str) -> str:
    match = re.search(r"数量[:：]\s*([0-9]+)", html)
    if match:
        return match.group(1).strip()

    return ""


def fetch_detail(session: requests.Session, seed_id: str) -> str:
    params = {
        "openId": OPEN_ID,
        "sid": SID,
        "id": seed_id,
    }

    resp = session.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()

    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "ascii"}:
        resp.encoding = resp.apparent_encoding or "utf-8"

    return resp.text

def extract_income(html: str) -> str:
    # 匹配：预计收入：10000金币，只保留 10000
    match = re.search(r"预计收入[:：]\s*([0-9]+)\s*金币", html)
    if match:
        return match.group(1).strip()

    # 兜底：只要预计收入后面有数字就提取
    match = re.search(r"预计收入[:：]\s*([0-9]+)", html)
    if match:
        return match.group(1).strip()

    return ""


def calculate_hourly_income(income: str, mature_time: str) -> str:
    try:
        income_value = float(income)
        mature_time_value = float(mature_time)
    except ValueError:
        return ""

    if mature_time_value <= 0:
        return ""

    value = income_value / mature_time_value
    return f"{value:.2f}".rstrip("0").rstrip(".")


def main():
    seeds = read_seeds(SEEDS_FILE)

    if not seeds:
        print(f"没有从 {SEEDS_FILE} 读取到种子数据")
        return

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        )
    })

    results = []

    for index, (seed_id, crop_name) in enumerate(seeds, start=1):
        try:
            html = fetch_detail(session, seed_id)

            mature_time = extract_mature_time(html)
            quantity = extract_quantity(html)
            income = extract_income(html)
            hourly_income = calculate_hourly_income(income, mature_time)

            print(
                f"[{index}/{len(seeds)}] "
                f"{seed_id}\t{crop_name}\t{mature_time or '未提取到'}\t"
                f"{quantity or '未提取到'}\t{income or '未提取到'}\t{hourly_income or '未计算'}"
            )

            results.append({
                "种子ID": seed_id,
                "作物名称": crop_name,
                "成熟时间": mature_time,
                "数量": quantity,
                "预计收入": income,
                "每小时收益": hourly_income,
            })

        except Exception as e:
            print(f"[{index}/{len(seeds)}] {seed_id}\t{crop_name}\t请求失败：{e}")

            results.append({
                "种子ID": seed_id,
                "作物名称": crop_name,
                "成熟时间": "",
                "数量": "",
                "预计收入": "",
                "每小时收益": "",
            })

        time.sleep(0.1)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["种子ID", "作物名称", "成熟时间", "预计收入", "每小时收益", "数量"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\n完成，结果已保存到：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
