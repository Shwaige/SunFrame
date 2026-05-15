# merge_mature_inventory.py
import csv
from pathlib import Path


MATURE_FILE = "mature_result.tsv"
INVENTORY_FILE = "inventory_result.csv"
OUTPUT_FILE = "mature_inventory_result.csv"


def inventory_to_seed_id(inventory_id: str) -> str:
    return inventory_id[:-1] if inventory_id else ""


def read_mature(path: str) -> dict[str, dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = csv.DictReader(f, delimiter="\t")
        return {row["种子ID"]: row for row in rows}


def read_inventory(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    mature_by_id = read_mature(MATURE_FILE)
    inventory_rows = read_inventory(INVENTORY_FILE)

    results: list[dict[str, str]] = []
    for inventory in inventory_rows:
        seed_id = inventory_to_seed_id(inventory["作物ID"])
        mature = mature_by_id.get(seed_id)
        if not mature:
            continue

        results.append(
            {
                "种子ID": seed_id,
                "作物ID": inventory["作物ID"],
                "作物名称": mature["作物名称"],
                "分类": inventory["分类"],
                "成熟时间": mature["成熟时间"],
                "预计收入": mature["预计收入"],
                "每小时收益": mature["每小时收益"],
                "数量": mature["数量"],
                "已有数量": inventory["已有数量"],
                "是否制标": inventory["是否制标"],
            }
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "种子ID",
                "作物ID",
                "作物名称",
                "分类",
                "成熟时间",
                "预计收入",
                "每小时收益",
                "数量",
                "已有数量",
                "是否制标",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print(
        f"完成，成熟数据 {len(mature_by_id)} 条，仓库数据 {len(inventory_rows)} 条，"
        f"ID 匹配 {len(results)} 条，结果已保存到：{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
