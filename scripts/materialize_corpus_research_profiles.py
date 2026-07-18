"""Materialize validated corpus (team × map) into discoverable research profiles.

Reads only already-normalized CSV/metadata from ``data/processed/`` and uses
``data/series/*/coverage_summary.json`` for tier filtering.  Generates the
manifest + 3-piece suit (``series_metadata.json``, ``precontact_opening_samples.csv``,
``precontact_opening_profile.csv``) at locations that
``research_catalog.discover_research_profiles()`` can detect.

Usage:
    python scripts/materialize_corpus_research_profiles.py ^
        --processed-root data/processed/iem-cologne-major-2026-corpus ^
        --coverage data/series/iem-cologne-major-2026-corpus/coverage_summary.json ^
        --series-root data/series ^
        --tiers standard
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent

sys.path.insert(0, str(_PROJECT_ROOT))

from src.team_map_series import (  # noqa: E402
    ECONOMY_SAMPLE_SECONDS,
    load_team_map_series,
    opening_profile,
    precontact_opening_samples,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
METADATA_FILENAME = "metadata.json"
DEFAULT_SAMPLE_SECOND = 20.0

# Files that make a profile "complete" per discover_research_profiles()
REQUIRED_ARTIFACTS = (
    "series_metadata.json",
    "precontact_opening_samples.csv",
    "precontact_opening_profile.csv",
)

# CSV fieldnames for the results log
RESULT_FIELDS = [
    "profile_id", "team", "map", "tier",
    "match_count", "status", "reason",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_filename(name: str) -> str:
    """Lower-case, alphanumeric-and-underscore safe slug."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
    return safe or "unknown"


def _profile_id(team: str, map_name: str) -> str:
    """Stable, non-colliding profile ID for one team × map."""
    slug = _safe_filename(team)
    return f"iem-cologne-2026-{slug}-{map_name}"


def _parse_tiers(raw: str) -> set[str]:
    """Parse comma-separated tier list and validate."""
    tiers = {t.strip().lower() for t in raw.split(",") if t.strip()}
    valid = {"standard", "exploratory", "insufficient"}
    unknown = tiers - valid
    if unknown:
        raise ValueError(f"未知 tier 值：{', '.join(sorted(unknown))}。有效值：{', '.join(sorted(valid))}")
    return tiers


def _read_coverage(coverage_path: Path) -> list[dict]:
    """Load coverage_summary.json and return its coverage list."""
    raw = json.loads(coverage_path.read_text(encoding="utf-8"))
    entries = raw.get("coverage", [])
    if not isinstance(entries, list):
        raise ValueError("coverage_summary.json 缺少 coverage 列表")
    return entries


def _read_metadata_safe(metadata_path: Path) -> dict | None:
    """Read and validate a bundle metadata.json.  Returns None on failure."""
    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


# ---------------------------------------------------------------------------
# Core scanning
# ---------------------------------------------------------------------------


def _scan_import_results(results_csv: Path) -> list[dict[str, str]]:
    """Read import_results.csv and return only parsed_and_validated rows."""
    if not results_csv.is_file():
        raise FileNotFoundError(f"找不到 import_results.csv：{results_csv}")

    rows: list[dict[str, str]] = []
    with results_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status", "").strip() == "parsed_and_validated":
                rows.append(row)
    return rows


def _build_match_lookup(
    import_rows: list[dict[str, str]],
    processed_root: Path,
) -> dict[tuple[str, str], dict]:
    """Build (match_id, map) -> metadata dict from metadata.json on disk.

    Returns only entries where metadata.json exists, is valid, and its
    ``import_status`` (if present) is ``parsed_and_validated``.
    """
    lookup: dict[tuple[str, str], dict] = {}
    for row in import_rows:
        match_id = row.get("match_id", "").strip()
        map_name = row.get("map", "").strip()
        if not match_id or not map_name:
            continue
        key = (match_id, map_name)
        metadata_path = processed_root / match_id / map_name / METADATA_FILENAME
        meta = _read_metadata_safe(metadata_path)
        if meta is None:
            # metadata.json missing -> cannot verify team; skip silently
            continue

        # If metadata has an import_status field, require parsed_and_validated
        status = str(meta.get("import_status", "parsed_and_validated")).strip()
        if status != "parsed_and_validated":
            continue

        lookup[key] = meta
    return lookup


def _group_matches_by_team_map(
    match_lookup: dict[tuple[str, str], dict],
    processed_root: Path,
    manifest_parent: Path,
) -> dict[tuple[str, str], list[dict]]:
    """Group validated matches by (team, map).

    For each match, extracts the target team's perspective and builds a
    manifest entry with a correctly resolvable bundle path.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}

    for (match_id, map_name), meta in match_lookup.items():
        team_a = str(meta.get("team_a", "")).strip()
        team_b = str(meta.get("team_b", "")).strip()
        match_map = str(meta.get("map_name", "")).strip().lower()
        if not team_a or not team_b or not match_map:
            continue

        # Build a relative bundle path: from manifest_parent down to the bundle dir
        bundle_abs = (processed_root / match_id / map_name).resolve()
        try:
            bundle_rel = os.path.relpath(str(bundle_abs), str(manifest_parent.resolve()))
        except ValueError:
            bundle_rel = str(bundle_abs)

        entry = {
            "id": match_id,
            "bundle": bundle_rel,
            "event": str(meta.get("event", "")).strip() or "IEM Cologne Major 2026",
            "stage": str(meta.get("stage", "")).strip(),
        }

        for team in (team_a, team_b):
            opponent = team_b if team == team_a else team_a
            team_entry = dict(entry)
            team_entry["opponent"] = opponent
            key = (team, map_name)
            grouped.setdefault(key, []).append(team_entry)

    return grouped


# ---------------------------------------------------------------------------
# Profile materialization
# ---------------------------------------------------------------------------


def _is_profile_complete(series_dir: Path) -> bool:
    """Return True when all three required artifacts exist."""
    return all((series_dir / name).is_file() for name in REQUIRED_ARTIFACTS)


def _materialize_one_profile(
    team: str,
    map_name: str,
    match_entries: list[dict],
    tier: str,
    manifest_path: Path,
    series_dir: Path,
    *,
    dry_run: bool,
    sample_second: float = DEFAULT_SAMPLE_SECOND,
) -> dict:
    """Build one profile (manifest + 3-piece suit) for a single team × map.

    Returns a result dict suitable for the results CSV.
    """
    profile_id = _profile_id(team, map_name)
    match_count = len(match_entries)

    if not match_entries:
        return {
            "profile_id": profile_id,
            "team": team,
            "map": map_name,
            "tier": tier,
            "match_count": 0,
            "status": "skipped",
            "reason": "没有匹配的比赛项",
        }

    if dry_run:
        return {
            "profile_id": profile_id,
            "team": team,
            "map": map_name,
            "tier": tier,
            "match_count": match_count,
            "status": "planned",
            "reason": f"{match_count} 场比赛待构建",
        }

    # If profile already exists and is complete, skip.
    if manifest_path.is_file() and _is_profile_complete(series_dir):
        return {
            "profile_id": profile_id,
            "team": team,
            "map": map_name,
            "tier": tier,
            "match_count": match_count,
            "status": "skipped",
            "reason": "已存在且三件套完整",
        }

    try:
        # --- Write manifest ---
        manifest_data = {
            "team": team,
            "map": map_name,
            "season": "IEM Cologne Major 2026",
            "coverage_tier": tier,
            "parsed_match_count": match_count,
            "boundary": (
                "样本等级是覆盖提示，不是战术结论。经济标签描述冻结结束装备证据，"
                "不等于购买意图或默认战术。"
            ),
            "matches": match_entries,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # --- Build 3-piece suit via existing logic ---
        series = load_team_map_series(manifest_path)
        samples = precontact_opening_samples(series, sample_second=sample_second)
        profile = opening_profile(samples)

        series_dir.mkdir(parents=True, exist_ok=True)
        samples.to_csv(series_dir / "precontact_opening_samples.csv", index=False)
        profile.to_csv(series_dir / "precontact_opening_profile.csv", index=False)

        economy_ready = (
            samples["economy_scope"].eq("freeze_end_snapshot").any()
        )
        economy_counts = {
            str(label): int(count)
            for label, count in (
                samples.loc[samples["sample_eligible"], "economy_label"]
                .value_counts()
                .items()
            )
        }
        metadata = {
            "team": series.team,
            "map": series.map_name,
            "season": series.season,
            "coverage_tier": tier,
            "match_count": len(series.matches),
            "parsed_match_count": match_count,
            "sample_second": sample_second,
            "economy_sample_seconds": ECONOMY_SAMPLE_SECONDS,
            "total_round_samples": len(samples),
            "eligible_precontact_samples": int(
                samples["sample_eligible"].sum()
            ),
            "economy_scope": (
                "freeze_end_snapshot" if economy_ready else "unclassified"
            ),
            "economy_label_counts": economy_counts,
            "boundary": (
                "Only samples before the first observed opposing-team damage "
                "(or first kill when damage events are unavailable). Known "
                "economy labels use documented observation checkpoints; this "
                "does not identify a set play or a team tendency. Economy "
                "labels describe freeze-end loadout evidence only."
            ),
        }
        (series_dir / "series_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "profile_id": profile_id,
            "team": team,
            "map": map_name,
            "tier": tier,
            "match_count": match_count,
            "status": "ok",
            "reason": "",
        }

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return {
            "profile_id": profile_id,
            "team": team,
            "map": map_name,
            "tier": tier,
            "match_count": match_count,
            "status": "failed",
            "reason": reason,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "把已验证 corpus 中的 team × map 组合变成网页研究台可发现的 "
            "完整 profile（manifest + 三件套）。"
        )
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        required=True,
        help="已规范化数据的根目录（含 import_results.csv 及各 bundle）",
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        required=True,
        help="coverage_summary.json 路径",
    )
    parser.add_argument(
        "--series-root",
        type=Path,
        required=True,
        help="data/series/ 根目录，profile manifest 和目录写在此下",
    )
    parser.add_argument(
        "--tiers",
        type=str,
        default="standard",
        help="逗号分隔的 tier 列表（默认 standard），例如 'standard,exploratory'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多处理 N 个 profile（0 = 全部）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出计划，不创建任何文件",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="结果 CSV 路径（默认写到 corpus series 根目录）",
    )
    parser.add_argument(
        "--sample-second",
        type=float,
        default=DEFAULT_SAMPLE_SECOND,
        help="每回合接触前观察秒数（默认 20）",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # ---- Validate inputs ----
    processed_root = args.processed_root.resolve()
    coverage_path = args.coverage.resolve()
    series_root = args.series_root.resolve()

    if not processed_root.is_dir():
        parser.error(f"processed-root 不存在或不是目录：{processed_root}")
    if not coverage_path.is_file():
        parser.error(f"coverage 文件不存在：{coverage_path}")
    if not series_root.is_dir():
        parser.error(f"series-root 不存在或不是目录：{series_root}")

    tiers = _parse_tiers(args.tiers)
    limit = args.limit
    dry_run = args.dry_run
    sample_second = args.sample_second

    # ---- Load coverage ----
    coverage_entries = _read_coverage(coverage_path)
    # Filter by requested tiers
    filtered = [c for c in coverage_entries if c.get("tier", "").strip().lower() in tiers]
    if not filtered:
        print(f"coverage 中没有 tier 为 {args.tiers} 的条目，退出。")
        return

    # Apply limit
    if limit > 0:
        filtered = filtered[:limit]

    print(
        f"coverage 总计 {len(coverage_entries)} 项，"
        f"筛选 tier={args.tiers} 后 {len(filtered)} 项"
        f"{'（limit={})'.format(limit) if limit else ''}"
    )

    # ---- Build match lookup from processed bundles ----
    results_csv_path = processed_root / "import_results.csv"
    import_rows = _scan_import_results(results_csv_path)

    if not import_rows:
        print("警告：import_results.csv 中没有 parsed_and_validated 的行", file=sys.stderr)
    match_lookup = _build_match_lookup(import_rows, processed_root)

    if not match_lookup:
        print("警告：无法从 processed bundle 读取任何有效的 metadata.json", file=sys.stderr)

    # ---- Group matches by (team, map) ----
    # This will be used to provide match entries for each coverage entry.
    # The manifest_parent is series_root (where *.json manifests sit).
    grouped = _group_matches_by_team_map(
        match_lookup, processed_root, series_root
    )

    # ---- Materialize profiles ----
    results: list[dict] = []

    for entry in filtered:
        team = str(entry.get("team", "")).strip()
        map_name = str(entry.get("map", "")).strip()
        tier = str(entry.get("tier", "")).strip().lower()
        count = int(entry.get("parsed_match_count", 0))

        if not team or not map_name:
            results.append({
                "profile_id": "",
                "team": team,
                "map": map_name,
                "tier": tier,
                "match_count": count,
                "status": "skipped",
                "reason": "coverage 条目缺少 team 或 map",
            })
            continue

        profile_id = _profile_id(team, map_name)
        manifest_path = series_root / f"{profile_id}.json"
        series_dir = series_root / profile_id

        # Get match entries from the processed-data scan
        match_entries = grouped.get((team, map_name), [])

        if not match_entries:
            result = {
                "profile_id": profile_id,
                "team": team,
                "map": map_name,
                "tier": tier,
                "match_count": count,
                "status": "failed",
                "reason": "processed 数据中找不到对应队伍/地图的已解析比赛",
            }
        else:
            result = _materialize_one_profile(
                team,
                map_name,
                match_entries,
                tier,
                manifest_path,
                series_dir,
                dry_run=dry_run,
                sample_second=sample_second,
            )

        results.append(result)

        # Brief progress line
        status = result["status"]
        reason = f" — {result['reason']}" if result.get("reason") else ""
        print(f"  {status:>8}  {profile_id}{reason}")

    # ---- Write results CSV ----
    if args.results:
        result_path = args.results.resolve()
    else:
        result_path = coverage_path.parent / "materialize_results.csv"

    with result_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    # ---- Summary ----
    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    print()
    print(f"结果已写入：{result_path}")
    status_summary = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
    print(f"概要：{status_summary}")
    if dry_run:
        print("（--dry-run 模式，未写入任何 profile 文件）")


if __name__ == "__main__":
    main()
