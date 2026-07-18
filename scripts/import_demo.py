"""Parse one CS2 .dem and write a reproducible analysis bundle.

Example:
    python scripts/import_demo.py path\\to\\mirage.dem --output data\\processed\\furia-falcons-mirage
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.awpy_adapter import load_awpy_demo, write_normalized_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a CS2 demo into CS Tactical Lens tables.")
    parser.add_argument("demo", type=Path, help="Path to one .dem file")
    parser.add_argument("--output", type=Path, required=True, help="Directory for CSV tables and metadata")
    args = parser.parse_args()
    if args.demo.suffix.lower() != ".dem":
        parser.error("只接受 .dem 文件；请先从下载包中解压出单张地图的 demo。")
    if not args.demo.is_file():
        parser.error(f"找不到 demo：{args.demo}")
    data = load_awpy_demo(args.demo)
    destination = write_normalized_bundle(data, args.output)
    print(f"已生成：{destination}")
    print(f"{data.match_name} | {data.map_name} | {data.team_a} vs {data.team_b} | {len(data.rounds)} rounds")


if __name__ == "__main__":
    main()
