import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS = [
    "extract_seeds.py",
    "extract_mature.py",
    "extract_inventory.py",
    "merge_mature_inventory.py",
]


def run_script(script_name: str) -> None:
    print(f"\n========== {script_name} ==========\n")
    subprocess.run([sys.executable, script_name], cwd=SCRIPT_DIR, check=True)


def main() -> int:
    for script_name in SCRIPTS:
        run_script(script_name)
    print("\n全部完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
