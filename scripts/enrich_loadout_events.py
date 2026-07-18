"""Add event-compressed post-freeze loadout timelines to existing bundles.

The script reparses the source demo but writes only ``loadout_events.csv`` and
its metadata audit fields. It never overwrites rounds, positions, economy
snapshots or any existing replay evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_match_archives import _find_7z  # noqa: E402
from import_match_archives import (  # noqa: E402
    _canonicalize_team_names,
    _extract_one,
    _read_candidates,
    _registry,
    _validate,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.awpy_adapter import load_awpy_demo  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="为已有 Demo bundle 补充 V3.2 装备变化事件流")
    parser.add_argument("catalog", type=Path, help="按地图生成的 demos.csv")
    parser.add_argument("--registry", type=Path, required=True, help="比赛 registry JSON")
    parser.add_argument("--output", type=Path, required=True, help="已有 bundle 输出根目录")
    parser.add_argument("--target-team", default="Team Falcons")
    parser.add_argument("--expected-players", required=True, help="逗号分隔的阵容，用于 Demo 校验")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--match-slug", help="只处理指定比赛 slug，适合定点重建")
    parser.add_argument("--replace-existing", action="store_true", help="按当前规则重建已有事件文件")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = _read_candidates(args.catalog)
    registry = _registry(args.registry)
    candidates = [row for row in candidates if row["match_slug"] in registry]
    if args.match_slug:
        candidates = [row for row in candidates if row["match_slug"] == args.match_slug]
    if args.limit:
        candidates = candidates[:args.limit]
    if not candidates:
        parser.error("没有找到已登记且目标地图匹配的 Demo")

    seven_zip = None if args.dry_run else _find_7z()
    expected_players = {
        player.strip().lower() for player in args.expected_players.split(",") if player.strip()
    }
    results: list[dict[str, str]] = []
    for index, row in enumerate(candidates, start=1):
        bundle = args.output / row["match_slug"] / row["map"]
        output_path = bundle / "loadout_events.csv"
        if not bundle.is_dir():
            results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "missing_bundle"})
            print(f"{index:02d}. 缺少 bundle：{row['match_slug']}")
            continue
        # A few HLTV archives split one map into p1/p2 demo members.  The
        # existing bundle has already recorded the member that was accepted
        # during import, so never let a sibling segment overwrite or enrich it.
        metadata_path = bundle / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("source_member") and metadata["source_member"] != row["demo_member"]:
            results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "skipped_noncanonical_segment"})
            print(f"{index:02d}. 跳过非登记片段：{row['demo_member']}")
            continue
        if output_path.is_file() and not args.replace_existing:
            results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "already_present"})
            print(f"{index:02d}. 已存在：{row['match_slug']}")
            continue
        print(f"{index:02d}. {row['match_slug']} <- {Path(row['source_file']).name} :: {row['demo_member']}")
        if args.dry_run:
            results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "pending"})
            continue
        with tempfile.TemporaryDirectory(prefix="cs-demo-loadout-") as temp_dir:
            demo_path = _extract_one(row, Path(temp_dir) / row["demo_member"], seven_zip)
            data = load_awpy_demo(demo_path)
            _validate(data, row, registry[row["match_slug"]], args.target_team, expected_players)
            data = _canonicalize_team_names(data, registry[row["match_slug"]])
            if data.loadout_events.empty:
                results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "no_events"})
                continue
            data.loadout_events.to_csv(output_path, index=False)
            metadata["loadout_event_status"] = "parsed_and_validated"
            metadata["loadout_event_rows"] = int(len(data.loadout_events))
            metadata["loadout_event_columns"] = list(data.loadout_events.columns)
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            results.append({"match_slug": row["match_slug"], "map": row["map"], "status": "parsed_and_validated"})

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "loadout_event_enrichment_results.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["match_slug", "map", "status"])
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
