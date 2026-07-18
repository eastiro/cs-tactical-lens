r"""Generate per-team series manifests from a shared import_results.csv.

After a registry-driven batch import completes, run this script to create
one series manifest JSON per team for the imported map.

Usage::

    python scripts/build_registry_series_manifests.py
        --registry data/registry/iem-cologne-major-2026-match-registry.json
        --import-results data/processed/iem-cologne-major-2026-stage3-playoffs-dust2/import_results.csv
        --map de_dust2
        --output-dir data/series/iem-cologne-major-2026-stage3-playoffs-dust2

"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path


def _load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_results(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 import_results.csv：{path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _safe_filename(name: str) -> str:
    """Turn a team name into a safe filename fragment."""
    safe = re.sub(r"[^a-zA-Z0-9一-鿿_-]", "_", name.strip().lower())
    return safe or "unknown"


def _build_manifests(
    registry: dict,
    results: list[dict[str, str]],
    target_map: str,
    output_dir: Path,
) -> list[Path]:
    """Generate one manifest per team, return list of created paths."""
    # Build registry lookup: match_id -> {teams, stage, match_page_url}
    reg_lookup: dict[str, dict] = {}
    for rec in registry.get("records", []):
        reg_lookup[rec["match_id"]] = rec

    # Collect validated results per team
    # team -> [manifest_entry]
    team_entries: dict[str, list[dict]] = {}

    for row in results:
        if row.get("status") != "parsed_and_validated":
            continue
        match_id = row.get("match_id", "")
        map_name = row.get("map", "")
        if map_name != target_map:
            continue

        reg_rec = reg_lookup.get(match_id)
        if not reg_rec:
            continue  # skip results whose match_id isn't in registry

        registry_teams = reg_rec.get("teams", [])
        stage = reg_rec.get("stage", "")
        raw_bundle = Path(row.get("bundle", "").replace("\\", "/"))
        # Older catalogs already store a manifest-relative path (../processed).
        # Registry-batch results store a project-root-relative path
        # (data/processed).  Support both without rewriting old manifests.
        bundle_already_relative = not raw_bundle.is_absolute() and raw_bundle.parts and raw_bundle.parts[0] == ".."
        bundle_abs = raw_bundle if raw_bundle.is_absolute() else (Path.cwd() / raw_bundle).resolve()

        # Determine opponent for each team
        if len(registry_teams) >= 2:
            t0, t1 = registry_teams[0], registry_teams[1]
            # Get event name from registry or infer
            event = "IEM Cologne Major 2026"
            date = ""

            for t in registry_teams:
                team_entries.setdefault(t, [])
                opponent = t1 if t == t0 else t0
                manifest_path = output_dir / f"{_safe_filename(t)}-{target_map}.json"
                if bundle_already_relative:
                    bundle_value = raw_bundle.as_posix()
                try:
                    bundle_value = bundle_value if bundle_already_relative else os.path.relpath(bundle_abs, manifest_path.parent)
                except ValueError:
                    # Windows cannot express a relative path across drives.
                    # Keep an absolute path for external/test manifests; normal
                    # project manifests remain portable relative paths.
                    bundle_value = str(bundle_abs)
                entry = {
                    "id": match_id,
                    "bundle": bundle_value,
                    "opponent": opponent,
                    "event": event,
                    "stage": stage,
                }
                if date:
                    entry["date"] = date
                # Avoid duplicate match_id entries for the same team
                if not any(e["id"] == match_id for e in team_entries[t]):
                    team_entries[t].append(entry)

    created: list[Path] = []
    for team in sorted(team_entries):
        matches = team_entries[team]
        # Remove duplicates by match_id (safety check)
        seen_ids: set[str] = set()
        unique_matches = []
        for m in matches:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                unique_matches.append(m)

        manifest = {
            "team": team,
            "map": target_map,
            "season": "IEM Cologne Major 2026",
            "notes": f"从注册表批量导入生成。{target_map} 候选样本，队伍名已规范化。",
            "matches": unique_matches,
        }

        safe_name = _safe_filename(team)
        manifest_path = output_dir / f"{safe_name}-{target_map}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        created.append(manifest_path)

    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从共享 import_results 为每支参赛队生成 series manifest"
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--import-results", type=Path, required=True)
    parser.add_argument("--map", required=True, help="目标地图，如 de_dust2")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.registry.is_file():
        parser.error(f"找不到注册表：{args.registry}")

    try:
        results = _load_results(args.import_results)
    except FileNotFoundError as e:
        parser.error(str(e))

    registry = _load_registry(args.registry)
    validated = [r for r in results if r.get("status") == "parsed_and_validated"]
    if not validated:
        parser.error(
            f"import_results.csv 中没有 status=parsed_and_validated 的结果。"
            f"请先运行导入器。"
        )

    created = _build_manifests(registry, results, args.map, args.output_dir)

    if not created:
        print("未生成任何 manifest（没有已验证结果或匹配的比赛）。")
        sys.exit(1)

    print(f"已生成 {len(created)} 个 series manifest：")
    for p in created:
        print(f"  {p}")
    teams = [p.stem.split("-" + args.map.replace("_", "-"))[0] for p in created]
    print(f"\n涉及队伍：{', '.join(teams)}")


if __name__ == "__main__":
    main()
