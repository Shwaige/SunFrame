# Rare Seed Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个单账号脚本，读取稀有种子商店中“已有”的种子，查询其详情页中的成熟时间，并输出到控制台。

**Architecture:** 复用现有项目中的 `requests + HTML 正则解析` 思路，但不接入现有 `ygmc` CLI。脚本独立放在 `get_seeds/` 目录下，直接请求商店分页页，提取“已有”的种子 `seedId`，再访问 `goodsInfo.go` 详情页解析成熟时间。输出保持纯控制台文本，不写 CSV，不改现有结果文件。

**Tech Stack:** Python 3、requests、正则表达式、标准库 HTML 反转义

---

## File Structure

- Create: `get_seeds/query_rare_seed_inventory.py`
- Modify: none
- Test: 以 `python3 -m py_compile get_seeds/query_rare_seed_inventory.py` 做语法校验；再实际运行脚本验证输出

### Task 1: 实现独立查询脚本

**Files:**
- Create: `get_seeds/query_rare_seed_inventory.py`
- Test: `get_seeds/query_rare_seed_inventory.py`

- [ ] **Step 1: 写出脚本骨架和常量**

```python
from __future__ import annotations

import html
import re
from dataclasses import dataclass

import requests


STORE_URL = "http://mc.pinpinhu.com/ygmc/store/index.go"
GOODS_INFO_URL = "http://mc.pinpinhu.com/ygmc/store/goodsInfo.go"
OPEN_ID = "fb881448c456f31cb8c2f854762a6aff"
SID = "b50ba491b26dba4c1bc2f2b0f2c786280c90ba1b"
TIMEOUT = 10


@dataclass(frozen=True)
class SeedSummary:
    seed_id: str
    name: str


@dataclass(frozen=True)
class SeedDetail:
    seed_id: str
    name: str
    mature_time: str
```

- [ ] **Step 2: 实现请求函数和分页解析**

```python
def fetch_store_page(session: requests.Session, page_no: int) -> str:
    response = session.get(
        STORE_URL,
        params={
            "openId": OPEN_ID,
            "sid": SID,
            "ver": "0",
            "type": "0",
            "subType": "2",
            "pageNo": str(page_no),
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_total_pages(page: str) -> int:
    match = re.search(r"第\\s*\\d+\\s*/\\s*(\\d+)页", page)
    if not match:
        return 1
    return max(1, int(match.group(1)))
```

- [ ] **Step 3: 实现“已有稀有种子”解析**

```python
def parse_owned_seeds(page: str) -> list[SeedSummary]:
    results: list[SeedSummary] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"id=([A-Za-z0-9_]+)[^>]*>\\[种子\\]([^<]+)</a>(.*?)<br/?\\s*>",
        re.I | re.S,
    )
    for seed_id, raw_name, tail in pattern.findall(page):
        if "已有" not in html.unescape(tail):
            continue
        if seed_id in seen:
            continue
        seen.add(seed_id)
        results.append(SeedSummary(seed_id=seed_id, name=html.unescape(raw_name).strip()))
    return results
```

- [ ] **Step 4: 实现详情页请求和成熟时间解析**

```python
def fetch_goods_info(session: requests.Session, seed_id: str) -> str:
    response = session.get(
        GOODS_INFO_URL,
        params={
            "openId": OPEN_ID,
            "sid": SID,
            "ver": "0",
            "id": seed_id,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_mature_time(page: str) -> str:
    text = html.unescape(re.sub(r"<.*?>", "", page, flags=re.S))
    match = re.search(r"成熟时间[:：]\\s*([^\\n\\r]+)", text)
    if match:
        return match.group(1).strip()
    return "未解析到成熟时间"
```

- [ ] **Step 5: 实现主流程和控制台输出**

```python
def main() -> int:
    session = requests.Session()
    all_seeds: dict[str, SeedSummary] = {}

    try:
        first_page = fetch_store_page(session, 1)
    except Exception as exc:
        print(f"请求商店失败：{exc}")
        return 1

    total_pages = parse_total_pages(first_page)
    for seed in parse_owned_seeds(first_page):
        all_seeds[seed.seed_id] = seed

    for page_no in range(2, total_pages + 1):
        try:
            page = fetch_store_page(session, page_no)
        except Exception as exc:
            print(f"请求第 {page_no} 页失败：{exc}")
            continue
        for seed in parse_owned_seeds(page):
            all_seeds[seed.seed_id] = seed

    if not all_seeds:
        print("未发现已有稀有种子")
        return 0

    for seed in all_seeds.values():
        try:
            detail_page = fetch_goods_info(session, seed.seed_id)
            mature_time = parse_mature_time(detail_page)
        except Exception as exc:
            print(f"种子ID={seed.seed_id} 名称={seed.name} 成熟时间=查询失败 错误={exc}")
            continue
        print(f"种子ID={seed.seed_id} 名称={seed.name} 成熟时间={mature_time}")

    return 0


if __name__ == \"__main__\":
    raise SystemExit(main())
```

- [ ] **Step 6: 运行语法校验**

Run:

```bash
python3 -m py_compile get_seeds/query_rare_seed_inventory.py
```

Expected:

```text
无输出，退出码为 0
```

- [ ] **Step 7: 实际运行脚本验证输出**

Run:

```bash
python3 get_seeds/query_rare_seed_inventory.py
```

Expected:

```text
输出若干行“种子ID=... 名称=... 成熟时间=...”，或输出“未发现已有稀有种子”
```

- [ ] **Step 8: 提交**

```bash
git add get_seeds/query_rare_seed_inventory.py
git commit -m "新增稀有种子库存查询脚本"
```
