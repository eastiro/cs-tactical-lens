"""Create reusable team -> map catalog views from one shared match catalog.

These are references to source archives, not copied demo files.  A team that
only appears against Falcons is deliberately marked as a shared-opponent
sample; it becomes a complete team/map dataset only after more matches are
added to the registry.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import unicodedata


BASE_COLUMNS = [
    "team", "opponent", "event", "date", "dataset_scope", "source_file",
    "source_kind", "match_slug", "demo_member", "map", "is_target_map",
    "demo_size_bytes", "duplicate_key", "catalog_status",
]


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "unknown-team"


def _load_registry(path: Path) -> dict[str, dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("matches")
    if not isinstance(entries, list):
        raise ValueError("registry 的 matches 必须是列表")
    registry: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("registry 中存在非对象条目")
        match_slug = str(entry.get("match_slug", "")).strip()
        teams = entry.get("teams")
        if not match_slug or not isinstance(teams, list) or len(teams) != 2 or not all(isinstance(team, str) and team.strip() for team in teams):
            raise ValueError(f"registry 条目不完整：{entry}")
        if match_slug in registry:
            raise ValueError(f"registry match_slug 重复：{match_slug}")
        registry[match_slug] = entry
    return registry


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="由共享比赛目录生成按战队/地图浏览的索引视图")
    parser.add_argument("catalog", type=Path, help="catalog_match_archives.py 生成的 all_maps.csv")
    parser.add_argument("--registry", type=Path, required=True, help="比赛、日期与两队名称的 JSON 清单")
    parser.add_argument("--primary-team", required=True, help="本次采集的主队，用于标记完整采集口径")
    parser.add_argument("--output", type=Path, required=True, help="按战队输出的根目录")
    parser.add_argument("--minimum-maps", type=int, default=5, help="标记为可开始多场研究的最低单图场数，默认 5")
    args = parser.parse_args()
    registry = _load_registry(args.registry)
    with args.catalog.open(encoding="utf-8-sig", newline="") as handle:
        catalog_rows = list(csv.DictReader(handle))

    per_team_map: dict[tuple[str, str], list[dict[str, str]]] = {}
    unregistered: list[dict[str, str]] = []
    for row in catalog_rows:
        match = registry.get(row["match_slug"])
        if match is None:
            unregistered.append(row)
            continue
        teams = [str(team) for team in match["teams"]]
        for team in teams:
            opponent = next(name for name in teams if name != team)
            enriched = {
                "team": team,
                "opponent": opponent,
                "event": str(match.get("event", "")),
                "date": str(match.get("date", "")),
                "dataset_scope": (
                    "primary_team_collection" if team == args.primary_team
                    else "shared_matches_vs_primary_team_only"
                ),
                **{column: row.get(column, "") for column in BASE_COLUMNS[5:]},
            }
            per_team_map.setdefault((team, row["map"]), []).append(enriched)

    args.output.mkdir(parents=True, exist_ok=True)
    team_index: list[dict[str, object]] = []
    for (team, map_name), rows in sorted(per_team_map.items()):
        category = args.output / _slug(team) / "maps" / map_name
        category.mkdir(parents=True, exist_ok=True)
        _write_csv(category / "demos.csv", rows)
        metadata = {
            "team": team,
            "map": map_name,
            "demo_entries": len(rows),
            "unique_demo_candidates": len({row["duplicate_key"] for row in rows}),
            "dataset_scope": rows[0]["dataset_scope"],
            "boundary": "这是共享原始比赛包的索引视图，不复制 Demo；实际解析时仍校验地图、战队和阵容。",
        }
        (category / "category.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        team_index.append({"team": team, "map": map_name, **metadata})

    with (args.output / "team_map_index.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["team", "map", "demo_entries", "unique_demo_candidates", "dataset_scope", "boundary"])
        writer.writeheader()
        writer.writerows(team_index)
    gaps = [
        {
            "team": row["team"],
            "map": row["map"],
            "current_unique_matches": row["unique_demo_candidates"],
            "minimum_required": args.minimum_maps,
            "additional_matches_needed": max(0, args.minimum_maps - int(row["unique_demo_candidates"])),
            "dataset_scope": row["dataset_scope"],
        }
        for row in team_index
        if int(row["unique_demo_candidates"]) < args.minimum_maps
    ]
    with (args.output / "coverage_gaps.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["team", "map", "current_unique_matches", "minimum_required", "additional_matches_needed", "dataset_scope"],
        )
        writer.writeheader()
        writer.writerows(gaps)
    if unregistered:
        with (args.output / "unregistered_entries.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=catalog_rows[0].keys())
            writer.writeheader()
            writer.writerows(unregistered)
    print(f"已生成 {len(team_index)} 个战队/地图分类入口，覆盖 {len({row['team'] for rows in per_team_map.values() for row in rows})} 支队伍。")
    print(f"低于 {args.minimum_maps} 场的战队/地图组合：{len(gaps)} 个（见 coverage_gaps.csv）。")
    if unregistered:
        print(f"有 {len(unregistered)} 条未登记来源保留在 unregistered_entries.csv，未归入任何战队。")


if __name__ == "__main__":
    main()
