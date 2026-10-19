r"""Registry-driven batch importer for the IEM Cologne Major 2026 corpus.

Reads the match registry, selects candidates by ``--map`` and ``--stages``,
extracts-and-parses each demo, then writes a normalised bundle into
``<output>/<match_id>/<map>/``.

Reuses archive extraction, team validation, and name canonicalisation from
:doc:`import_match_archives.py` but **does not require a fixed five-man
roster** — it validates only that both registry teams appear in the demo.

Usage::

    python scripts/import_registry_batch.py
        --registry data/registry/iem-cologne-major-2026-match-registry.json
        --map de_dust2
        --stages stage-3,playoffs
        --output data/processed/iem-cologne-major-2026-stage3-playoffs-dust2
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

# Reuse team-matching helpers from import_match_archives
sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_match_archives import (  # noqa: E402
    _canonicalize_team_names,
    _team_matches,
)

# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def _select_candidates(
    registry: dict,
    target_map: str,
    target_stages: set[str] | None,
    target_teams: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Select candidates from the registry.

    Returns
        (candidates, blocked)
        where each candidate/blocked dict has:
            match_id, stage, teams, archive_path, members
    """
    candidates: list[dict] = []
    blocked: list[dict] = []

    for rec in registry.get("records", []):
        if rec.get("status") != "registered":
            continue
        stage = rec.get("stage", "")
        if target_stages and stage not in target_stages:
            continue
        # Optional team filter: match if record involves ANY target team
        if target_teams:
            rec_teams_lower = {t.lower() for t in rec.get("teams", [])}
            if not rec_teams_lower & target_teams:
                continue

        # Deduplicate members by map
        seen_maps: dict[str, list[dict]] = defaultdict(list)
        for m in rec.get("members", []):
            map_name = m.get("map", "")
            if map_name == target_map:
                seen_maps[map_name].append(m)

        if not seen_maps:
            continue

        entry = {
            "match_id": rec["match_id"],
            "stage": stage,
            "teams": rec["teams"],
            "archive_path": rec.get("archive_path", ""),
            "members": seen_maps[target_map],
        }

        if len(seen_maps[target_map]) == 1:
            candidates.append(entry)
        else:
            entry["reason"] = f"segmented: {len(seen_maps[target_map])} members for map {target_map}"
            blocked.append(entry)

    # Sort by match_id for stable ordering
    candidates.sort(key=lambda x: int(x["match_id"]))
    blocked.sort(key=lambda x: int(x["match_id"]))
    return candidates, blocked


# ---------------------------------------------------------------------------
# Archive extraction
# ---------------------------------------------------------------------------


def _extract_one(member: dict, archive_path: str, seven_zip: str | None, temp_dir: str) -> Path:
    """Extract a single .dem member from an archive into *temp_dir*."""
    source = Path(archive_path)
    suffix = source.suffix.lower()
    dest = Path(temp_dir) / member["member"]

    if suffix == ".dem":
        # Bare .dem — copy, don't extract (archive_path IS the demo)
        shutil.copy2(source, dest)
        return dest

    if not seven_zip:
        raise RuntimeError("需要 7-Zip 才能从 RAR/7z 整场包抽取单张地图。")

    result = subprocess.run(
        [seven_zip, "e", "-so", str(source), member["member"]],
        stdout=dest.open("wb"),
        stderr=subprocess.PIPE,
        text=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"抽取失败：{Path(archive_path).name} / {member['member']}："
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return dest


# ---------------------------------------------------------------------------
# Validation (no fixed roster)
# ---------------------------------------------------------------------------


def _validate_teams(data: Any, registry_teams: list[str]) -> None:
    """Validate that both registry teams appear in the parsed demo."""
    observed = [str(data.team_a), str(data.team_b)]
    for expected in registry_teams:
        if not any(_team_matches(expected, actual) for actual in observed):
            raise ValueError(
                f"队伍校验失败：registry 写 {expected}，Demo 中观察到 {observed}"
            )


def _load_plan_cohort_ids(plan_path: Path, target_map: str) -> set[str]:
    """Extract recommended match IDs for *target_map* from the import plan."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cohorts = plan.get("recommended_first_cohort", [])
    for rec in cohorts:
        if rec.get("map") == target_map:
            ids = set(rec.get("related_match_ids", []))
            if not ids:
                raise ValueError(
                    f"推荐项目 {target_map} 的 related_match_ids 为空"
                )
            return ids
    raise ValueError(
        f"规划中未找到地图 {target_map} 的推荐批次。"
        f"可用地图：{[c['map'] for c in cohorts if 'map' in c]}"
    )



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="注册表驱动的批量 Demo 导入器——抽取、校验、规范化并构建 bundle"
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--map", required=True, help="目标地图，如 de_dust2")
    parser.add_argument(
        "--stages", default=None,
        help="逗号分隔的 stage 过滤，如 stage-3,playoffs（默认全部）",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个候选（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="只列出队列，不解压不解析")
    parser.add_argument(
        "--teams", default=None,
        help="逗号分隔的队伍名过滤，如 Falcons,Spirit（不区分大小写；默认全部）",
    )
    parser.add_argument(
        "--plan", type=Path, default=None,
        help="iem-cologne-major-2026-import-plan.json 路径，将候选限定为推荐 cohort 的 match IDs",
    )
    args = parser.parse_args()

    if not args.registry.is_file():
        parser.error(f"找不到注册表：{args.registry}")

    target_stages: set[str] | None = None
    if args.stages:
        target_stages = {s.strip() for s in args.stages.split(",")}

    target_teams: set[str] | None = None
    if args.teams:
        target_teams = {t.strip().lower() for t in args.teams.split(",")}

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    candidates, blocked = _select_candidates(registry, args.map, target_stages, target_teams)

    # Plan-based narrowing: restrict to recommended cohort match IDs
    plan_match_ids: set[str] | None = None
    plan_note = ""
    if args.plan:
        if not args.plan.is_file():
            parser.error(f"找不到规划文件：{args.plan}")
        try:
            plan_match_ids = _load_plan_cohort_ids(args.plan, args.map)
        except ValueError as e:
            parser.error(str(e))
        candidates = [c for c in candidates if c["match_id"] in plan_match_ids]
        blocked = [b for b in blocked if b["match_id"] in plan_match_ids]
        plan_note = f"（来源：recommended_first_cohort/{args.map}，规划 {len(plan_match_ids)} ID，候选 {len(candidates)}）"
        if not candidates:
            # Only error if no candidates remain AND no candidates before plan (i.e. plan IDs exist but don't match)
            if plan_match_ids:
                print(f"规划推荐 {len(plan_match_ids)} 个 match ID，但无一在候选列表中。")
                print(f"推荐的 ID：{sorted(plan_match_ids)}")
                sys.exit(1)

    if not candidates and not blocked:
        print("没有找到候选或阻塞的地图样本。")
        sys.exit(1)

    apply_limit = args.limit > 0
    limited_to = args.limit if apply_limit else len(candidates)
    selected = candidates[:limited_to] if apply_limit else candidates

    print(f"目标地图：{args.map}")
    print(f"Stage 过滤：{args.stages or '全部'}")
    print(f"候选数：{len(candidates)}")
    print(f"Blocked（多 member）：{len(blocked)}")
    if plan_note:
        print(plan_note)
    if apply_limit:
        print(f"Limit 后：{limited_to}")
    print()

    # Print candidate list
    print("==" * 30)
    print("候选列表：")
    for i, c in enumerate(selected, 1):
        teams_str = " vs ".join(c["teams"])
        fname = Path(c["archive_path"]).name
        member_name = c["members"][0]["member"]
        print(f"  {i:2d}. [{c['stage']}] {c['match_id']}  {teams_str}")
        print(f"       archive: {fname}")
        print(f"       member:  {member_name}")
    print()

    if blocked:
        print("Blocked（多 member / segmented）：")
        for i, b in enumerate(blocked, 1):
            teams_str = " vs ".join(b["teams"])
            print(f"  {i:2d}. [{b['stage']}] {b['match_id']}  {teams_str}  — {b.get('reason', '')}")
        print()

    if args.dry_run:
        source = f"（来源：recommended_first_cohort/{args.map}）" if args.plan else "（来源：全量 registry）"
        s = f"Dry-run 完成：{len(selected)} 个可导入、{len(blocked)} 个 segmented_blocked、0 个文件写入 {source}"
        print("==" * 30)
        print(s)
        return

    # ── Actual import ──
    seven_zip = _find_7z()
    results: list[dict[str, str]] = []
    results_path = args.output / "import_results.csv"
    # Resume: metadata is the source of truth.  A process can be interrupted
    # after a bundle is fully written but before import_results.csv is flushed.
    # In that case, using the CSV alone would needlessly parse a large demo
    # again (and could overwrite an already verified bundle).
    existing_results: dict[tuple[str, str], str] = {}
    for c in selected:
        match_id = c["match_id"]
        bundle_path = args.output / match_id / args.map
        metadata_path = bundle_path / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("import_status") != "parsed_and_validated":
            continue
        if str(metadata.get("match_id")) != match_id:
            continue
        existing_results[(match_id, args.map)] = "parsed_and_validated"
        results.append({
            "match_id": match_id,
            "map": args.map,
            "stage": c["stage"],
            "teams": " vs ".join(c["teams"]),
            "bundle": str(bundle_path),
            "status": "parsed_and_validated",
        })

    for index, c in enumerate(selected, start=1):
        match_id = c["match_id"]
        map_name = args.map

        # Skip already-parsed
        if (match_id, map_name) in existing_results:
            print(f"[{index}/{len(selected)}] 已跳过（已验证）：{match_id}")
            continue

        member = c["members"][0]
        try:
            with tempfile.TemporaryDirectory(prefix="cs-import-") as tmp_dir:
                demo_path = _extract_one(member, c["archive_path"], seven_zip, tmp_dir)
                data = load_awpy_demo(demo_path)

                # Validate map
                if str(data.map_name).strip().lower() != map_name.lower():
                    raise ValueError(
                        f"地图校验失败：请求 {map_name}，解析出 {data.map_name}"
                    )
                # Validate teams (no fixed roster)
                _validate_teams(data, c["teams"])
                # Canonicalize
                registry_obj = {"teams": c["teams"]}
                data = _canonicalize_team_names(data, registry_obj)

                bundle_path = args.output / match_id / map_name
                write_normalized_bundle(data, bundle_path)

                # Update metadata
                meta_path = bundle_path / "metadata.json"
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                metadata.update({
                    "match_id": match_id,
                    "stage": c["stage"],
                    "event": "IEM Cologne Major 2026",
                    "source_archive": c["archive_path"],
                    "source_member": member["member"],
                    "teams": c["teams"],
                    "import_status": "parsed_and_validated",
                    "team_names_canonicalized": True,
                    "importer": "import_registry_batch.py",
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                })
                meta_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            results.append({
                "match_id": match_id, "map": map_name,
                "stage": c["stage"],
                "teams": " vs ".join(c["teams"]),
                "bundle": str(bundle_path),
                "status": "parsed_and_validated",
            })
            print(f"[{index}/{len(selected)}] 已完成：{match_id} / {map_name}")

        except Exception as exc:
            msg = f"[{index}/{len(selected)}] 失败：{match_id} / {member['member']}：{exc}"
            print(msg, file=sys.stderr)
            results.append({
                "match_id": match_id, "map": map_name,
                "stage": c["stage"],
                "teams": " vs ".join(c["teams"]),
                "bundle": "",
                "status": f"error: {exc}",
            })
            # Continue with next candidate rather than aborting the whole batch
            continue

    # Write results CSV
    args.output.mkdir(parents=True, exist_ok=True)
    fieldnames = ["match_id", "map", "stage", "teams", "bundle", "status"]
    with results_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    parsed = sum(1 for r in results if r["status"] == "parsed_and_validated")
    errors = sum(1 for r in results if r["status"].startswith("error"))
    print(f"\n导入完成：{parsed} 已解析，{errors} 失败，{len(blocked)} 被阻塞")


if __name__ == "__main__":
    main()
