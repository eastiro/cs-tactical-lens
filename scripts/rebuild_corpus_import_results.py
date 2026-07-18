"""Rebuild a corpus import_results.csv from validated bundle metadata.

Use after an interrupted process/OS crash leaves the CSV empty while already
written normalized bundles remain valid on disk.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="从已验证 bundle 重建全量导入结果表")
    parser.add_argument("--output", type=Path, required=True, help="corpus 输出根目录")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for metadata_path in sorted(args.output.glob("*/*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("import_status") != "parsed_and_validated":
            continue
        match_id = str(metadata.get("match_id", "")).strip()
        if not match_id:
            continue
        teams = metadata.get("teams", [])
        rows.append({
            "match_id": match_id,
            "map": metadata_path.parent.name,
            "stage": str(metadata.get("stage", "")),
            "teams": " vs ".join(str(team) for team in teams),
            "bundle": str(metadata_path.parent),
            "status": "parsed_and_validated",
        })
    rows.sort(key=lambda row: (int(row["match_id"]), row["map"]))
    destination = args.output / "import_results.csv"
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["match_id", "map", "stage", "teams", "bundle", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"已重建 {len(rows)} 条已验证结果：{destination}")


if __name__ == "__main__":
    main()
