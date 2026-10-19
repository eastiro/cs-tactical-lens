r"""Full-corpus batch importer for IEM Cologne Major 2026.

Enumerates every registered ``(match\_id, map)`` from the match registry,
classifies each as ``ready`` / ``segmented_blocked``, and drives the existing
parse-validate-canonicalise pipeline.

Supports resume: already-parsed bundles are skipped.  All results accumulate
in a single ``import_results.csv`` (not overwritten per-map).

Usage::

    python scripts/import_registry_corpus.py
        --registry data/registry/iem-cologne-major-2026-match-registry.json
        --output data/processed/iem-cologne-major-2026-corpus
        --dry-run

"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_match_archives import _find_7z  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.awpy_adapter import load_awpy_demo, write_normalized_bundle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_match_archives import (  # noqa: E402
    _canonicalize_team_names,
    _team_matches,
)

# ---------------------------------------------------------------------------
# Candidate enumeration
# ---------------------------------------------------------------------------


def _enumerate_candidates(
    registry: dict,
    filter_maps: set[str] | None = None,
    filter_stages: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Enumerate all (match_id, map) from the registry.

    Returns
        (ready, segmented_blocked, missing)
    """
    ready: list[dict] = []
    segmented: list[dict] = []
    missing: list[dict] = []

    for rec in registry.get("records", []):
        stage = rec.get("stage", "")
        if filter_stages and stage not in filter_stages:
            continue
        if rec.get("status") == "missing_archive":
            missing.append({
                "match_id": rec["match_id"],
                "stage": stage,
                "teams": rec.get("teams", []),
                "reason": "missing_archive",
            })
            continue
        if rec.get("status") != "registered":
            continue

        members = rec.get("members", [])
        if not members:
            missing.append({
                "match_id": rec["match_id"],
                "stage": stage,
                "teams": rec["teams"],
                "reason": "no_members_in_registry",
            })
            continue

        # Group members by map
        map_groups: dict[str, list[dict]] = defaultdict(list)
        for m in members:
            map_name = m.get("map", "")
            if filter_maps and map_name not in filter_maps:
                continue
            map_groups[map_name].append(m)

        for map_name, group in map_groups.items():
            entry = {
                "match_id": rec["match_id"],
                "stage": stage,
                "teams": rec["teams"],
                "archive_path": rec.get("archive_path", ""),
                "map": map_name,
                "members": group,
            }
            if len(group) == 1:
                ready.append(entry)
            else:
                entry["reason"] = f"segmented: {len(group)} members"
                segmented.append(entry)

    # Sort stably
    ready.sort(key=lambda x: (int(x["match_id"]), x["map"]))
    segmented.sort(key=lambda x: (int(x["match_id"]), x["map"]))
    missing.sort(key=lambda x: int(x["match_id"]))
    return ready, segmented, missing


# ---------------------------------------------------------------------------
# Extraction & validation (reused from import_registry_batch.py)
# ---------------------------------------------------------------------------


def _extract_one(member: dict, archive_path: str, seven_zip: str | None, temp_dir: str) -> Path:
    source = Path(archive_path)
    suffix = source.suffix.lower()
    dest = Path(temp_dir) / member["member"]
    if suffix == ".dem":
        shutil.copy2(source, dest)
        return dest
    if not seven_zip:
        raise RuntimeError("需要 7-Zip 才能从 RAR/7z 整场包抽取单张地图。")
    result = subprocess.run(
        [seven_zip, "e", "-so", str(source), member["member"]],
        stdout=dest.open("wb"), stderr=subprocess.PIPE, text=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"抽取失败：{Path(archive_path).name} / {member['member']}："
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return dest


def _validate_teams(data: Any, registry_teams: list[str]) -> None:
    observed = [str(data.team_a), str(data.team_b)]
    for expected in registry_teams:
        if not any(_team_matches(expected, actual) for actual in observed):
            raise ValueError(f"队伍校验失败：registry 写 {expected}，Demo 中观察到 {observed}")


# ---------------------------------------------------------------------------
# Resume helpers
# ---------------------------------------------------------------------------


def _load_existing_results(results_path: Path) -> dict[tuple[str, str], str]:
    """Load existing import_results.csv and return {(match_id, map): status}."""
    existing: dict[tuple[str, str], str] = {}
    if not results_path.is_file():
        return existing
    with results_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            existing[(row["match_id"], row["map"])] = row["status"]
    return existing


def _bundle_is_done(output_root: Path, match_id: str, map_name: str) -> bool:
    """Check if a bundle has already been successfully parsed."""
    meta = output_root / match_id / map_name / "metadata.json"
    if not meta.is_file():
        return False
    try:
        md = json.loads(meta.read_text(encoding="utf-8"))
        return md.get("import_status") == "parsed_and_validated"
    except (OSError, json.JSONDecodeError):
        return False


def _member_bundle_map(output_root: Path, match_id: str, member_name: str) -> str | None:
    """Find a completed bundle by source member, even if its filename map was wrong."""
    for meta in (output_root / match_id).glob("*/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("import_status") == "parsed_and_validated" and data.get("source_member") == member_name:
            return meta.parent.name
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IEM Cologne Major 2026 全量 corpus 导入总控"
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个 ready（0=全部）")
    parser.add_argument("--maps", default=None, help="逗号分隔的地图过滤，如 de_dust2,de_mirage")
    parser.add_argument("--stages", default=None, help="逗号分隔的 stage 过滤，如 stage-3,playoffs")
    args = parser.parse_args()

    if not args.registry.is_file():
        parser.error(f"找不到注册表：{args.registry}")

    filter_maps: set[str] | None = None
    if args.maps:
        filter_maps = {s.strip() for s in args.maps.split(",")}
    filter_stages: set[str] | None = None
    if args.stages:
        filter_stages = {s.strip() for s in args.stages.split(",")}

    registry = json.loads(args.registry.read_text(encoding="utf-8"))

    # -- Enumerate
    ready, segmented, missing = _enumerate_candidates(
        registry, filter_maps, filter_stages,
    )

    apply_limit = args.limit > 0
    limited = ready[:args.limit] if apply_limit else ready

    # -- Summary
    print("全量 corpus 扫描完成")
    print(f"  Registered 比赛：{sum(1 for r in registry['records'] if r.get('status') == 'registered')}")
    print(f"  Ready（单 member）：{len(ready)}")
    print(f"  Segmented blocked：{len(segmented)}")
    print(f"  Missing archive：{len(missing)}")
    if apply_limit:
        print(f"  Limit 后：{len(limited)}")
    if filter_maps:
        print(f"  地图过滤：{sorted(filter_maps)}")
    if filter_stages:
        print(f"  Stage 过滤：{sorted(filter_stages)}")

    # -- Per-stage, per-map breakdown
    stage_map_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in ready:
        stage_map_counts[c["stage"]][c["map"]] += 1
    print()
    print("Ready 分 stage/map：")
    for stage in sorted(stage_map_counts):
        maps_str = ", ".join(
            f"{m}:{n}" for m, n in sorted(stage_map_counts[stage].items())
        )
        print(f"  {stage}: {maps_str}")
    print()

    # Dry-run: write Markdown report
    if args.dry_run:
        md_path = args.output / "corpus-dry-run.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        lines.append("# IEM Cologne Major 2026 — Corpus Dry-run 报告\n")
        lines.append(f"> 生成时间：{datetime.now(timezone.utc).isoformat()}\n")
        lines.append("## 概览\n")
        lines.append(f"- Registered 比赛：{sum(1 for r in registry['records'] if r.get('status') == 'registered')}")
        lines.append(f"- Ready（单 member，可导入）：**{len(ready)}**")
        lines.append(f"- Segmented blocked：**{len(segmented)}**")
        lines.append(f"- Missing archive：**{len(missing)}**")
        lines.append("")
        lines.append("### 分 stage/map 统计（Ready）\n")
        lines.append("| Stage | Map | Ready 数 |")
        lines.append("|------|-----|---------|")
        for stage in sorted(stage_map_counts):
            for map_name in sorted(stage_map_counts[stage]):
                lines.append(f"| {stage} | {map_name} | {stage_map_counts[stage][map_name]} |")
        lines.append("")
        if segmented:
            lines.append("### Segmented Blocked\n")
            lines.append("| match ID | Stage | 对阵 | 地图 | 原因 |")
            lines.append("|----------|-------|------|------|------|")
            for c in segmented:
                lines.append(
                    f"| {c['match_id']} | {c['stage']} | {' vs '.join(c['teams'])} | {c['map']} | {c.get('reason', '')} |"
                )
            lines.append("")
        if missing:
            lines.append("### Missing Archive\n")
            lines.append("| match ID | Stage | 对阵 |")
            lines.append("|----------|-------|------|")
            for c in missing:
                lines.append(f"| {c['match_id']} | {c['stage']} | {' vs '.join(c['teams'])} |")
            lines.append("")
        lines.append("---\n")
        lines.append(f"**共 {len(ready)} 个可导入、{len(segmented)} 个 blocked、{len(missing)} 个缺失。0 个文件写入。**\n")
        md_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Dry-run 报告：{md_path}")
        print(f"Dry-run 完成：{len(limited)} 个可导入、{len(segmented)} 个 segmented_blocked、0 个文件写入")
        return

    # -- Actual import
    # A batch limit is a safety limit for *new work*.  Completed bundles must
    # not consume the whole quota merely because they sort before the next
    # unfinished map.
    if apply_limit:
        pending: list[dict] = []
        for candidate in ready:
            member_name = candidate["members"][0]["member"]
            if _bundle_is_done(args.output, candidate["match_id"], candidate["map"]):
                continue
            if _member_bundle_map(args.output, candidate["match_id"], member_name):
                continue
            pending.append(candidate)
            if len(pending) >= args.limit:
                break
        limited = pending
        print(f"  本轮新任务：{len(limited)}")

    seven_zip = _find_7z()
    results_path = args.output / "import_results.csv"

    # Load existing results (for resume across maps)
    existing = _load_existing_results(results_path)
    # Also check metadata.json on disk (source of truth)
    all_results: list[dict[str, str]] = []
    # Preserve results from previous runs for maps NOT in this batch
    for (mid, mn), st in existing.items():
        if (not filter_maps or mn in filter_maps) and (not filter_stages or any(
            r["stage"] == s for r in registry.get("records", [])
            if r["match_id"] == mid for s in ([filter_stages] if isinstance(filter_stages, set) else [])
        )):
            # Keep existing result for maps in our scope
            pass
        all_results.append({
            "match_id": mid, "map": mn,
            "stage": "", "teams": "", "bundle": "", "status": st,
        })

    # Clear the in-scope results, they'll be re-generated
    in_scope = {(c["match_id"], c["map"]) for c in limited}
    all_results = [r for r in all_results if (r["match_id"], r["map"]) not in in_scope]

    def persist_results() -> dict[tuple[str, str], dict[str, str]]:
        """Checkpoint after every map so progress survives interruption."""
        args.output.mkdir(parents=True, exist_ok=True)
        deduped = {(r["match_id"], r["map"]): r for r in all_results}
        with results_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["match_id", "map", "stage", "teams", "bundle", "status"])
            writer.writeheader()
            writer.writerows(deduped.values())
        return deduped

    for index, c in enumerate(limited, start=1):
        match_id = c["match_id"]
        map_name = c["map"]

        # Skip if already done
        if _bundle_is_done(args.output, match_id, map_name):
            bundle_path = args.output / match_id / map_name
            all_results.append({
                "match_id": match_id, "map": map_name,
                "stage": c["stage"],
                "teams": " vs ".join(c["teams"]),
                "bundle": str(bundle_path),
                "status": "parsed_and_validated",
            })
            print(f"[{index}/{len(limited)}] 已跳过（已验证）：{match_id} / {map_name}")
            persist_results()
            continue

        member = c["members"][0]
        if actual_map := _member_bundle_map(args.output, match_id, member["member"]):
            bundle_path = args.output / match_id / actual_map
            all_results.append({
                "match_id": match_id, "map": actual_map,
                "stage": c["stage"], "teams": " vs ".join(c["teams"]),
                "bundle": str(bundle_path), "status": "parsed_and_validated",
            })
            print(f"[{index}/{len(limited)}] 已跳过（已按真实地图验证）：{match_id} / {actual_map}")
            persist_results()
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="cs-corpus-") as tmp_dir:
                demo_path = _extract_one(member, c["archive_path"], seven_zip, tmp_dir)
                data = load_awpy_demo(demo_path)

                actual_map = str(data.map_name).strip().lower()
                if not actual_map.startswith("de_"):
                    raise ValueError(f"Demo 未返回有效地图名：{data.map_name!r}")
                map_corrected = actual_map != map_name.lower()
                _validate_teams(data, c["teams"])
                registry_obj = {"teams": c["teams"]}
                data = _canonicalize_team_names(data, registry_obj)

                bundle_path = args.output / match_id / actual_map
                write_normalized_bundle(data, bundle_path)

                meta_path = bundle_path / "metadata.json"
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                metadata.update({
                    "match_id": match_id,
                    "stage": c["stage"],
                    "event": "IEM Cologne Major 2026",
                    "source_archive": c["archive_path"],
                    "source_member": member["member"],
                    "provisional_member_map": map_name,
                    "map_label_corrected": map_corrected,
                    "teams": c["teams"],
                    "import_status": "parsed_and_validated",
                    "team_names_canonicalized": True,
                    "importer": "import_registry_corpus.py",
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                })
                meta_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            all_results.append({
                "match_id": match_id, "map": actual_map,
                "stage": c["stage"],
                "teams": " vs ".join(c["teams"]),
                "bundle": str(bundle_path),
                "status": "parsed_and_validated",
            })
            note = f"（文件名地图 {map_name} 已校正）" if map_corrected else ""
            print(f"[{index}/{len(limited)}] 已完成：{match_id} / {actual_map}{note}")
            persist_results()

        except Exception as exc:
            msg = f"[{index}/{len(limited)}] 失败：{match_id} / {map_name}：{exc}"
            print(msg, file=sys.stderr)
            all_results.append({
                "match_id": match_id, "map": map_name,
                "stage": c["stage"],
                "teams": " vs ".join(c["teams"]),
                "bundle": "",
                "status": f"error: {exc}",
            })
            persist_results()
            continue

    # Write results CSV (accumulate, don't overwrite other maps)
    deduped = persist_results()

    parsed = sum(1 for r in deduped.values() if r["status"] == "parsed_and_validated")
    errors = sum(1 for r in deduped.values() if r["status"].startswith("error"))
    print(f"\n导入完成：{parsed} 已解析，{errors} 失败，{len(segmented)} 被阻塞")


if __name__ == "__main__":
    main()
