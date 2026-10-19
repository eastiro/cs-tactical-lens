r"""Build the IEM Cologne Major 2026 match registry.

Binds every match ID from the seed manifest + PLAYOFFS to its actual archive
on disk (from the raw-corpus inventory).  Output is a structured registry
with per-match status: ``registered``, ``missing_archive``, or
``ambiguous_archive``.

Usage::

    python scripts/build_cologne_match_registry.py
        --inventory reports/raw-corpus-inventory.json
        --output data/registry/iem-cologne-major-2026-match-registry.json
        --report reports/iem-cologne-major-2026-registry-report.md

"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED = ROOT / "data" / "intake-seeds" / "iem-cologne-major-2026-stage2-stage3-match-pages.json"
DOWNLOAD_SCRIPT = ROOT / "scripts" / "download_cologne_major_2026.py"

# Known team name slugs (longest first for greedy matching)
KNOWN_TEAMS_SLUG = sorted([
    "spirit", "betboom", "mibr", "9z", "fut", "b8", "g2", "monte",
    "gamerlegion", "m80", "flyquest", "astralis", "tyloo", "legacy",
    "big", "pain", "furia", "mouz", "natus-vincere", "aurora",
    "vitality", "falcons", "the-mongolz", "parivision",
], key=len, reverse=True)

# Stage name mapping: seed key → inventory stage label
STAGE_MAP = {
    "stage_2": "stage-2",
    "stage_3": "stage-3",
    "playoffs": "playoffs",
}


# ── helpers ────────────────────────────────────────────────────────────────


def _normalize_team(name: str) -> str:
    """Normalize a team name to a slug for archive-filename matching."""
    return name.strip().lower().replace(" ", "-").removeprefix("team-")


def _seed_team_slug(teams_str: str) -> tuple[str, str]:
    """Split ``"Team A vs Team B"`` into two normalised slugs."""
    parts = [p.strip() for p in teams_str.split(" vs ", 1)]
    return (_normalize_team(parts[0]), _normalize_team(parts[1]))


def _archive_team_slug(filename: str) -> tuple[str, str] | None:
    """Extract (team_a_slug, team_b_slug) from an archive filename."""
    name = filename.lower()
    for prefix in ["iem-cologne-major-2026-stage-2-", "iem-cologne-major-2026-"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    vs_idx = name.find("-vs-")
    if vs_idx == -1:
        return None
    left = name[:vs_idx]
    right = name[vs_idx + 4:]  # everything after "-vs-"
    # Match the longest known team at the start of right
    for team_slug in KNOWN_TEAMS_SLUG:
        if right == team_slug or right.startswith(team_slug + "-"):
            return (left, team_slug)
    return (left, None)  # right team not identified


def _teams_match(seed_a: str, seed_b: str, archive_a: str, archive_b: str) -> bool:
    """Check if two team pairs match (order-independent)."""
    seed = {seed_a, seed_b}
    archive = {archive_a, archive_b}
    return seed == archive


def _load_playoffs(download_script: Path | None = None) -> list[dict[str, str]]:
    """Parse PLAYOFFS list from download_cologne_major_2026.py."""
    path = download_script or DOWNLOAD_SCRIPT
    text = path.read_text(encoding="utf-8")
    # Extract the PLAYOFFS list literal
    match = re.search(
        r"PLAYOFFS\s*=\s*\[(.*?)\]", text, re.DOTALL
    )
    if not match:
        raise RuntimeError("Could not find PLAYOFFS list in download script")
    # Parse tuples: ("id", "teams", "url")
    entries: list[dict[str, str]] = []
    for line in match.group(1).splitlines():
        line = line.strip().strip(",")
        if not line or line.startswith("#"):
            continue
        # Match ("match_id", "teams", "url")
        parts = re.findall(r'"([^"]*)"', line)
        if len(parts) >= 3:
            entries.append({
                "match_id": parts[0],
                "teams": parts[1],
                "url": parts[2],
                "stage": "playoffs",
            })
    return entries


def _load_seed_matches(seed_path: Path | None = None,
                       download_script_path: Path | None = None) -> list[dict[str, str]]:
    """Load all 73 Cologne match entries from seed + PLAYOFFS."""
    path = seed_path or SEED
    seed = json.loads(path.read_text(encoding="utf-8"))
    matches: list[dict[str, str]] = []
    for stage_key, records in seed["stages"].items():
        for record in records:
            matches.append({
                "match_id": record["match_id"],
                "teams": record["teams"],
                "url": record["url"],
                "stage": stage_key,
            })
    matches.extend(_load_playoffs(download_script_path))
    # Deduplicate by match_id
    seen: set[str] = set()
    deduped = []
    for m in matches:
        if m["match_id"] not in seen:
            seen.add(m["match_id"])
            deduped.append(m)
    return sorted(deduped, key=lambda m: (m["stage"], int(m["match_id"])))


def _load_cologne_archives(inventory_path: Path) -> list[dict]:
    """Load Cologne-only archives from the inventory."""
    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    return [a for a in inv["archives"] if a.get("event") == "iem-cologne-major-2026"]


def _archive_match_key(filename: str, archive_stage: str | None) -> str | None:
    """Build a match key ``(stage, teamA_sorted, teamB_sorted)`` from the archive filename."""
    slugs = _archive_team_slug(filename)
    if slugs is None or slugs[1] is None:
        return None
    stage_key = archive_stage  # already in "stage-2", "stage-3", "playoffs" form
    sorted_teams = tuple(sorted(slugs))
    return f"{stage_key}::{sorted_teams[0]}::{sorted_teams[1]}"


def _seed_match_key(teams: str, seed_stage: str) -> str:
    """Build a match key ``(stage, teamA, teamB)`` from a seed entry."""
    a, b = _seed_team_slug(teams)
    stage_key = STAGE_MAP.get(seed_stage, seed_stage)
    # Order teams for deterministic matching
    sorted_teams = tuple(sorted([a, b]))
    return f"{stage_key}::{sorted_teams[0]}::{sorted_teams[1]}"


def _make_registry(
    seed_matches: list[dict[str, str]],
    cologne_archives: list[dict],
) -> dict:
    """Build the registry by binding archives to seed entries."""
    # Index archives by match key
    archive_by_key: dict[str, list[dict]] = defaultdict(list)
    for archive in cologne_archives:
        fname = archive["archive_path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        key = _archive_match_key(fname, archive.get("stage"))
        if key:
            archive_by_key[key].append(archive)

    # Stats
    stage_stats: dict[str, dict] = defaultdict(
        lambda: {"registered": 0, "missing": 0, "ambiguous": 0, "members": 0}
    )
    records: list[dict] = []
    missing_entries: list[dict] = []
    ambiguous_entries: list[dict] = []

    for match in seed_matches:
        seed_a, seed_b = _seed_team_slug(match["teams"])
        match_key = _seed_match_key(match["teams"], match["stage"])
        candidates = archive_by_key.get(match_key, [])
        stage_label = STAGE_MAP.get(match["stage"], match["stage"])

        teams_display = [
            t.replace("-", " ").title() for t in [seed_a, seed_b]
        ]
        record = {
            "match_id": match["match_id"],
            "stage": stage_label,
            "teams": teams_display,
            "match_page_url": match["url"],
        }

        # Check for single-map .dem that is a secondary copy
        # Primary = non-single-map-demos archive
        primary = [a for a in candidates
                   if a.get("sub_stage") != "single-map-demos"]
        secondary = [a for a in candidates
                     if a.get("sub_stage") == "single-map-demos"]

        if not candidates:
            record["status"] = "missing_archive"
            missing_entries.append(record)
        elif len(primary) == 1 or (not primary and len(candidates) == 1):
            # Exactly one primary archive (or only the single-map.dem)
            chosen = primary[0] if primary else candidates[0]
            record["archive_path"] = chosen["archive_path"]
            record["members"] = chosen["members"]
            record["status"] = "registered"
            if secondary:
                record["extra_archives"] = [a["archive_path"] for a in secondary]
            stage_stats[stage_label]["members"] += len(chosen["members"])
            stage_stats[stage_label]["registered"] += 1
        else:
            # Multiple primary archives → ambiguous
            record["status"] = "ambiguous_archive"
            record["reason"] = (
                f"找到 {len(primary)} 个主要 archive 匹配此比赛"
            )
            record["candidate_archives"] = [a["archive_path"] for a in primary]
            if secondary:
                record["candidate_archives"].extend(
                    [a["archive_path"] for a in secondary]
                )
            ambiguous_entries.append(record)
            stage_stats[stage_label]["ambiguous"] += 1

        records.append(record)

    # Fill remaining stats
    for rec in records:
        st = rec["stage"]
        if rec["status"] == "missing_archive":
            stage_stats[st]["missing"] += 1

    return {
        "event": "IEM Cologne Major 2026",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_match_ids": len(seed_matches),
        "summary": {
            "registered": sum(1 for r in records if r["status"] == "registered"),
            "missing_archive": sum(1 for r in records if r["status"] == "missing_archive"),
            "ambiguous_archive": sum(1 for r in records if r["status"] == "ambiguous_archive"),
        },
        "stage_summary": {
            stage: {
                "registered": s["registered"],
                "missing": s["missing"],
                "ambiguous": s["ambiguous"],
                "total_members": s["members"],
            }
            for stage, s in sorted(stage_stats.items())
        },
        "missing_entries": missing_entries,
        "ambiguous_entries": ambiguous_entries,
        "records": records,
        "boundary": "本注册表基于 seed manifest 与 archive 文件名匹配生成。不包含 demo 解析数据或已验证队伍/阵容。",
    }


def _build_md_report(registry: dict) -> str:
    """Render a Markdown registry report."""
    lines: list[str] = []
    lines.append("# IEM Cologne Major 2026 — 比赛注册表\n")
    lines.append(f"> 生成时间：{registry['generated_at']}\n")
    lines.append(registry["boundary"])
    lines.append("")

    s = registry["summary"]
    lines.append("## 总览\n")
    lines.append(f"- 总比赛数：{registry['total_match_ids']}")
    lines.append(f"- **registered**：{s['registered']}")
    lines.append(f"- **missing_archive**：{s['missing_archive']}")
    lines.append(f"- **ambiguous_archive**：{s['ambiguous_archive']}")
    lines.append("")

    lines.append("## 分阶段统计\n")
    lines.append("| 阶段 | Registered | Missing | Ambiguous | Demo member 数 |")
    lines.append("|------|-----------|--------|----------|---------------|")
    for stage in ["stage-2", "stage-3", "playoffs"]:
        ss = registry["stage_summary"].get(stage, {})
        lines.append(
            f"| {stage} | {ss.get('registered', 0)} | "
            f"{ss.get('missing', 0)} | {ss.get('ambiguous', 0)} | "
            f"{ss.get('total_members', 0)} |"
        )
    lines.append("")

    if registry["missing_entries"]:
        lines.append("## 缺失 Archive 的比赛\n")
        lines.append("| # | match ID | 对阵 | 阶段 |")
        lines.append("|---|---|---|---|")
        for i, m in enumerate(registry["missing_entries"], 1):
            lines.append(
                f"| {i} | {m['match_id']} | {' vs '.join(m['teams'])} | {m['stage']} |"
            )
        lines.append("")

    if registry["ambiguous_entries"]:
        lines.append("## 绑定模糊的比赛\n")
        lines.append("| # | match ID | 对阵 | 阶段 | 原因 |")
        lines.append("|---|---|---|---|---|")
        for i, m in enumerate(registry["ambiguous_entries"], 1):
            lines.append(
                f"| {i} | {m['match_id']} | {' vs '.join(m['teams'])} | "
                f"{m['stage']} | {m.get('reason', '')} |"
            )
        lines.append("")

    lines.append("---\n")
    lines.append(registry["boundary"])
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IEM Cologne Major 2026 比赛注册表——"
        "将 seed match ID 绑定到本地 archive"
    )
    parser.add_argument(
        "--inventory", type=Path, required=True,
        help="raw-corpus-inventory.json 路径",
    )
    parser.add_argument(
        "--seed", type=Path, default=None,
        help="seed JSON 路径（默认 data/intake-seeds/iem-cologne-major-2026-stage2-stage3-match-pages.json）",
    )
    parser.add_argument(
        "--download-script", type=Path, default=None,
        help="download_cologne_major_2026.py 路径（用于解析 PLAYOFFS，默认为 scripts/ 下）",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="注册表 JSON 输出路径",
    )
    parser.add_argument(
        "--report", type=Path, required=True,
        help="Markdown 报告输出路径",
    )
    args = parser.parse_args()

    if not args.inventory.is_file():
        parser.error(f"找不到 inventory 文件：{args.inventory}")

    seed_matches = _load_seed_matches(args.seed, args.download_script)
    cologne_archives = _load_cologne_archives(args.inventory)
    registry = _make_registry(seed_matches, cologne_archives)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"注册表 JSON：{args.output}")

    md = _build_md_report(registry)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(md, encoding="utf-8")
    print(f"注册表报告：{args.report}")

    s = registry["summary"]
    print("\nIEM Cologne Major 2026 注册表完成")
    print(f"  总比赛：{registry['total_match_ids']}")
    print(f"  Registered：{s['registered']}")
    print(f"  Missing：{s['missing_archive']}")
    print(f"  Ambiguous：{s['ambiguous_archive']}")


if __name__ == "__main__":
    main()
