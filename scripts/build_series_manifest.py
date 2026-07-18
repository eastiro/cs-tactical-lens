"""Build a team/map series manifest from validated import results."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="把批量导入结果整理成同队同图多场清单")
    parser.add_argument("import_results", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--team", required=True)
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--season", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry_raw = json.loads(args.registry.read_text(encoding="utf-8"))
    registry = {str(row["match_slug"]): row for row in registry_raw.get("matches", [])}
    with args.import_results.open(encoding="utf-8-sig", newline="") as handle:
        imported = list(csv.DictReader(handle))
    matches = []
    for row in imported:
        if row.get("map") != args.map_name or row.get("status") != "parsed_and_validated":
            continue
        entry = registry.get(row["match_slug"])
        if entry is None:
            raise ValueError(f"导入结果不在 registry 中：{row['match_slug']}")
        if entry.get("include", True) is False:
            continue
        teams = [str(team) for team in entry["teams"]]
        if args.team not in teams:
            raise ValueError(f"{row['match_slug']} 不包含目标队伍 {args.team}")
        bundle = Path(row["bundle"])
        if not bundle.is_absolute():
            bundle = (Path.cwd() / bundle).resolve()
        matches.append(
            {
                "id": row["match_slug"],
                "bundle": os.path.relpath(bundle, args.output.parent),
                "opponent": next(team for team in teams if team != args.team),
                "event": entry.get("event", ""),
                "date": entry.get("date", ""),
            }
        )
    if not matches:
        raise ValueError("没有可写入清单的已校验结果")
    payload = {
        "team": args.team,
        "map": args.map_name,
        "season": args.season,
        "notes": "只包含已解析、已校验的 bundle；接触前样本仍需按首次交火时间排除回合。",
        "matches": sorted(matches, key=lambda item: item["date"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成：{args.output}（{len(matches)} 场）")


if __name__ == "__main__":
    main()
