r"""Full-corpus series builder for IEM Cologne Major 2026.

Reads ``import_results.csv`` from the corpus importer, generates one series
manifest per ``team × map``, and produces a ``coverage_summary.json`` with
tier labels (``standard`` / ``exploratory`` / ``insufficient``).

Usage::

    python scripts/build_registry_corpus_series.py
        --registry data/registry/iem-cologne-major-2026-match-registry.json
        --import-results data/processed/iem-cologne-major-2026-corpus/import_results.csv
        --output-dir data/series/iem-cologne-major-2026-corpus

"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


def _load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_results(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 import_results.csv：{path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
    return safe or "unknown"


def _tier_label(count: int) -> str:
    if count >= 5:
        return "standard"
    elif count >= 3:
        return "exploratory"
    return "insufficient"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IEM Cologne Major 2026 全量 corpus series 构建总控"
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--import-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.registry.is_file():
        parser.error(f"找不到注册表：{args.registry}")

    try:
        results = _load_results(args.import_results)
    except FileNotFoundError as e:
        parser.error(str(e))

    registry = _load_registry(args.registry)
    reg_lookup: dict[str, dict] = {}
    for rec in registry.get("records", []):
        reg_lookup[rec["match_id"]] = rec

    # Group validated results by (team, map)
    # team_map -> {match_id -> entry}
    team_map_entries: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    # Track build results for CSV
    build_results: list[dict[str, str]] = []

    for row in results:
        if row.get("status") != "parsed_and_validated":
            continue
        match_id = row.get("match_id", "")
        map_name = row.get("map", "")
        reg_rec = reg_lookup.get(match_id)
        if not reg_rec:
            continue
        teams = reg_rec.get("teams", [])
        stage = reg_rec.get("stage", "")
        raw_bundle = row.get("bundle", "")

        # Determine relative bundle path from manifest location
        bundle_abs = Path(raw_bundle)
        if not bundle_abs.is_absolute():
            bundle_abs = (Path.cwd() / raw_bundle).resolve()

        for t in teams:
            opponent = teams[1] if t == teams[0] else teams[0]
            key = (t, map_name)
            if match_id not in team_map_entries[key]:
                team_map_entries[key][match_id] = {
                    "id": match_id,
                    "bundle": raw_bundle,
                    "opponent": opponent,
                    "event": "IEM Cologne Major 2026",
                    "stage": stage,
                }

    # Build manifests and coverage summary
    manifest_dir = args.output_dir / "manifests"
    coverage_rows: list[dict] = []

    for (team, map_name), matches in sorted(team_map_entries.items()):
        count = len(matches)
        unique_matches = list(matches.values())

        # Write manifest
        manifest = {
            "team": team,
            "map": map_name,
            "season": "IEM Cologne Major 2026",
            "notes": f"从全量 corpus 导入生成。{map_name} 候选样本，队伍名已规范化。",
            "matches": unique_matches,
        }
        safe_name = _safe_filename(team)
        manifest_path = manifest_dir / f"{safe_name}-{map_name}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        tier = _tier_label(count)
        coverage_rows.append({
            "team": team,
            "map": map_name,
            "parsed_match_count": count,
            "tier": tier,
        })
        build_results.append({
            "team": team, "map": map_name,
            "match_count": str(count), "status": "ok", "reason": "",
        })

    # Write coverage_summary.json
    summary = {
        "event": "IEM Cologne Major 2026",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "coverage": coverage_rows,
        "boundary": "覆盖状态仅反映已解析比赛数量，不代表战术结论或样本充足性。standard >= 5, exploratory 3-4, insufficient < 3。",
    }
    summary_path = args.output_dir / "coverage_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write series_build_results.csv
    csv_path = args.output_dir / "series_build_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["team", "map", "match_count", "status", "reason"])
        w.writeheader()
        w.writerows(build_results)

    # Print summary
    tiers = defaultdict(int)
    for c in coverage_rows:
        tiers[c["tier"]] += 1
    print("Series 构建完成")
    print(f"  生成 manifest：{len(team_map_entries)} 个")
    print(f"  覆盖状态：standard={tiers.get('standard', 0)}, exploratory={tiers.get('exploratory', 0)}, insufficient={tiers.get('insufficient', 0)}")
    print(f"  Manifest 目录：{manifest_dir}")
    print(f"  覆盖摘要：{summary_path}")


if __name__ == "__main__":
    main()
