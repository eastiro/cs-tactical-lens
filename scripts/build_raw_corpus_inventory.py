r"""Build a non-destructive raw-corpus inventory from ``data/raw/events/``.

This script produces a structured overview of every ``.dem`` member across all
archives — organised by **event**, **stage**, and **map** — without parsing or
extracting any demo file.

Outputs
    - JSON: per-member detail + aggregated summaries
    - Markdown: human-readable report with priority-candidate tables

Usage::

    python scripts/build_raw_corpus_inventory.py data/raw/events
        --output reports/raw-corpus-inventory.json
        --markdown reports/raw-corpus-inventory.md

"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight_demo_archives import (  # noqa: E402  # isort:skip
    ARCHIVE_SUFFIXES,
    _archive_members,
    _canonicalize,
    _find_7z,
    _map_name,
    _match_slug,
)
from preflight_demo_archives import DEMO_SUFFIX  # noqa: E402


def _extract_event_stage(
    archive_path: Path, events_root: Path,
) -> tuple[str, str | None, str | None]:
    """Parse the relative path under *events_root* into (event, stage, sub_stage).

    Examples
        ``events/iem-cologne-major-2026/stage-2/file.rar``  → ``("iem-cologne-major-2026", "stage-2", None)``
        ``events/iem-cologne-major-2026/playoffs/file.rar`` → ``("iem-cologne-major-2026", "playoffs", None)``
        ``events/iem-cologne-major-2026/playoffs/single-map-demos/file.dem``
                                                             → ``("iem-cologne-major-2026", "playoffs", "single-map-demos")``
        ``events/iem-rio-2026/file.rar``                     → ``("iem-rio-2026", None, None)``
    """
    try:
        rel = archive_path.resolve().relative_to(events_root.resolve())
    except ValueError:
        return ("unknown", None, None)

    parts = rel.parts  # e.g. ('iem-cologne', 'stage-2', 'file.rar')
    event = parts[0] if len(parts) >= 1 else "unknown"

    # The last part is always the filename — skip it.
    # Everything between parts[0] (event) and the filename is stage / sub_stage.
    dir_parts = parts[1:-1] if len(parts) > 1 else []

    stage = dir_parts[0] if len(dir_parts) >= 1 else None
    sub_stage = dir_parts[1] if len(dir_parts) >= 2 else None
    return (event, stage, sub_stage)


def _inventory_one(
    source: Path,
    events_root: Path,
    seven_zip: str | None,
) -> dict[str, object] | None:
    """Build a single archive entry with event/stage context."""
    suffix = source.suffix.lower()

    if suffix == DEMO_SUFFIX:
        size = source.stat().st_size
        member_name = source.name
        members = [
            {
                "member": member_name,
                "map": _map_name(member_name),
                "size_bytes": size,
                "match_slug": _match_slug(source),
                "duplicate_key": f"{Path(member_name).name.lower()}::{size}",
            }
        ]
        enum_status = "ok"
        error_msg = None
    elif suffix in ARCHIVE_SUFFIXES:
        members_raw, enum_status, error_msg = _archive_members(source, seven_zip)
        members = [
            {
                "member": member_name,
                "map": _map_name(member_name),
                "size_bytes": dem_size,
                "match_slug": _match_slug(source),
                "duplicate_key": f"{Path(member_name).name.lower()}::{dem_size}",
            }
            for member_name, dem_size in members_raw
        ]
    else:
        return None

    event, stage, sub_stage = _extract_event_stage(source, events_root)

    return {
        "archive_path": str(source.resolve()),
        "archive_suffix": suffix,
        "archive_size_bytes": source.stat().st_size,
        "event": event,
        "stage": stage,
        "sub_stage": sub_stage,
        "enumerate_status": enum_status,
        "error_message": error_msg,
        "members": members,
    }


def _build_aggregates(
    archives: list[dict[str, object]],
) -> dict[str, object]:
    """Build event/stage/map aggregations and duplicate detection."""
    all_members: list[dict[str, object]] = []

    # Per-event + per-stage aggregates
    event_map: dict[str, dict[str, object]] = {}

    for archive in archives:
        event = str(archive.get("event", "unknown"))
        stage = archive.get("stage")  # may be None
        stage_label: str = stage if stage else "(root)"

        if event not in event_map:
            event_map[event] = {"stages": {}, "total_archives": 0, "total_members": 0}
        event_map[event]["total_archives"] += 1
        event_map[event]["total_members"] += len(archive["members"])  # type: ignore[arg-type]

        stages = event_map[event]["stages"]  # type: ignore[union-attr]
        if stage_label not in stages:
            stages[stage_label] = {"total_archives": 0, "total_members": 0}
        stages[stage_label]["total_archives"] += 1
        stages[stage_label]["total_members"] += len(archive["members"])  # type: ignore[arg-type]

        all_members.extend(archive["members"])  # type: ignore[arg-type]

    # Per-event + per-stage + per-map aggregation for priority candidate table
    priority: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for archive in archives:
        event = str(archive.get("event", "unknown"))
        stage = archive.get("stage")
        stage_label: str = stage if stage else "(root)"
        for member in archive["members"]:  # type: ignore[arg-type]
            priority[event][stage_label][str(member["map"])] += 1

    event_summary = {}
    for event_name, data in sorted(event_map.items()):
        stage_summary = {}
        for stage_name, sdata in sorted(data["stages"].items()):  # type: ignore[arg-type]
            stage_summary[stage_name] = {
                "archives": sdata["total_archives"],
                "members": sdata["total_members"],
            }
        event_summary[event_name] = {
            "total_archives": data["total_archives"],
            "total_members": data["total_members"],
            "stages": stage_summary,
        }

    # Global map distribution
    map_counts: dict[str, int] = {}
    unknown = 0
    for member in all_members:
        m = str(member["map"])
        map_counts[m] = map_counts.get(m, 0) + 1
        if m == "unknown":
            unknown += 1

    # Duplicate candidates (same duplicate_key across archives)
    key_counts: dict[str, int] = {}
    for member in all_members:
        k = str(member["duplicate_key"])
        key_counts[k] = key_counts.get(k, 0) + 1
    duplicate_candidates = sum(1 for c in key_counts.values() if c > 1)

    # Priority candidate table
    priority_table: list[dict[str, object]] = []
    for event_name in sorted(priority):
        for stage_label in sorted(priority[event_name]):
            for map_name in sorted(priority[event_name][stage_label]):
                count = priority[event_name][stage_label][map_name]
                priority_table.append({
                    "event": event_name,
                    "stage": stage_label if stage_label != "(root)" else None,
                    "map": map_name,
                    "raw_candidate_count": count,
                    "disclaimer": "基于 archive member 文件名识别，未解析 demo 内容，未验证队伍或阵容。",
                })

    archives_needing_7zip = sum(
        1 for a in archives if a.get("enumerate_status") == "needs_7zip"
    )
    archives_with_errors = sum(
        1 for a in archives if a.get("enumerate_status") == "enumeration_error"
    )

    return {
        "total_archives": len(archives),
        "total_members": len(all_members),
        "archives_with_errors": archives_with_errors,
        "archives_needing_7zip": archives_needing_7zip,
        "events": event_summary,
        "global_map_distribution": dict(sorted(map_counts.items())),
        "unknown_map_count": unknown,
        "duplicate_candidate_count": duplicate_candidates,
        "priority_candidates": priority_table,
        "boundary": "本索引仅基于文件名和归档目录结构。不包含 demo 解析数据、已验证队伍或阵容。",
    }


def _build_markdown(
    aggregates: dict[str, object],
    archives: list[dict[str, object]],
) -> str:
    """Render a human-readable inventory report in UTF-8 Chinese."""
    lines: list[str] = []

    lines.append("# Raw Corpus 索引总览\n")
    lines.append(
        f"> 生成时间：{datetime.now(timezone.utc).isoformat()}\n"
    )
    lines.append(
        "本报告基于 `data/raw/events/` 目录中的 archive 文件名和归档结构生成。"
        "**未解析任何 demo 内容，未验证队伍或阵容。**\n"
    )

    # ── Summary numbers ──
    lines.append("## 全库概况\n")
    events_data = aggregates.get("events", {})
    lines.append(f"- **来源文件数**：{aggregates['total_archives']}")
    lines.append(f"- **Demo member 数**：{aggregates['total_members']}")
    lines.append(f"- **赛事数**：{len(events_data)}")
    lines.append(f"- **未知地图数**：{aggregates['unknown_map_count']}")
    lines.append(f"- **重复候选数**：{aggregates['duplicate_candidate_count']}")
    lines.append(f"- **枚举错误数**：{aggregates['archives_with_errors']}")
    lines.append(f"- **需要 7-Zip 数**：{aggregates['archives_needing_7zip']}\n")

    # ── Per-event breakdown ──
    lines.append("## 赛事分布\n")
    for event_name in sorted(events_data):
        edata = events_data[event_name]
        lines.append(f"### {event_name}\n")
        lines.append(f"- Archive 数：{edata['total_archives']}，Demo member 数：{edata['total_members']}")
        stages = edata.get("stages", {})
        if stages:
            lines.append("")
            lines.append("| 阶段 | Archive 数 | Demo member 数 |")
            lines.append("|------|-----------|---------------|")
            for stage_name in sorted(stages):
                sdata = stages[stage_name]
                lines.append(f"| {stage_name} | {sdata['archives']} | {sdata['members']} |")
        lines.append("")

    # ── Global map distribution ──
    lines.append("## 全库地图分布\n")
    lines.append("| 地图 | 数量 |")
    lines.append("|------|------|")
    for map_name, count in aggregates.get("global_map_distribution", {}).items():
        lines.append(f"| {map_name} | {count} |")
    lines.append("")

    # ── Priority candidate table ──
    lines.append("## 可优先导入候选\n")
    lines.append(
        "以下按 **赛事 × 阶段 × 地图** 聚合，列出每个组合的 raw 候选数。"
        "数值仅反映 archive member 文件名的地图识别结果，"
        "**不代表已解析、已验证队伍或已可在网站使用**。\n"
    )
    candidates = aggregates.get("priority_candidates", [])
    if candidates:
        lines.append("| # | 赛事 | 阶段 | 地图 | Raw 候选数 | 备注 |")
        lines.append("|---|---|---|---|---|---|")
        for i, c in enumerate(candidates, start=1):
            stage_display = c["stage"] if c["stage"] else "(根目录)"
            lines.append(
                f"| {i} | {c['event']} | {stage_display} | {c['map']} | {c['raw_candidate_count']} | 文件名候选，未验证 |"
            )
    else:
        lines.append("（无数据）")
    lines.append("")

    # ── Issues ──
    issues: list[str] = []
    if aggregates["archives_needing_7zip"]:
        issues.append(
            f"- {aggregates['archives_needing_7zip']} 个 archive 需要 7-Zip 才能枚举"
        )
    if aggregates["archives_with_errors"]:
        issues.append(
            f"- {aggregates['archives_with_errors']} 个 archive 枚举出错（见 JSON 中的 error_message）"
        )
    if aggregates["unknown_map_count"]:
        issues.append(
            f"- {aggregates['unknown_map_count']} 个 demo member 地图未知"
        )
    if aggregates["duplicate_candidate_count"]:
        issues.append(
            f"- {aggregates['duplicate_candidate_count']} 个重复候选（按 filename::size 判断）"
        )
    if issues:
        lines.append("## 注意事项\n")
        lines.extend(issues)
        lines.append("")

    # ── Delimiter ──
    lines.append("---\n")
    lines.append(
        "**边界声明**：本索引仅基于文件名和归档目录结构，不包含 demo 解析数据、"
        "已验证队伍或阵容。raw 候选数不应被等同于可用样本数。\n"
    )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raw Corpus 索引与覆盖审计——"
        "基于 data/raw/events/ 目录建立可审计的原始语料覆盖表"
    )
    parser.add_argument(
        "source", type=Path,
        help="events 根目录（如 data/raw/events）",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="JSON 输出路径",
    )
    parser.add_argument(
        "--markdown", type=Path, required=True,
        help="Markdown 报告输出路径",
    )
    args = parser.parse_args()

    if not args.source.is_dir():
        parser.error(f"找不到目录：{args.source}")

    seven_zip = _find_7z()

    archives: list[dict[str, object]] = []
    for entry in sorted(args.source.rglob("*")):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix == DEMO_SUFFIX or suffix in ARCHIVE_SUFFIXES:
            result = _inventory_one(entry, args.source, seven_zip)
            if result is not None:
                archives.append(result)

    if not archives:
        print("未在 events 目录下找到 .dem、.zip、.rar 或 .7z 文件。")
        sys.exit(1)

    archives = _canonicalize(archives)
    aggregates = _build_aggregates(archives)

    # JSON output
    report = {
        "inventory_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(args.source.resolve()),
        "total_archives": aggregates["total_archives"],
        "total_members": aggregates["total_members"],
        "events": aggregates["events"],
        "global_map_distribution": aggregates["global_map_distribution"],
        "unknown_map_count": aggregates["unknown_map_count"],
        "duplicate_candidate_count": aggregates["duplicate_candidate_count"],
        "archives_with_errors": aggregates["archives_with_errors"],
        "archives_needing_7zip": aggregates["archives_needing_7zip"],
        "priority_candidates": aggregates["priority_candidates"],
        "archives": archives,
        "boundary": aggregates["boundary"],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON 已输出：{args.output}")

    # Markdown output
    md = _build_markdown(aggregates, archives)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(md, encoding="utf-8")
    print(f"Markdown 已输出：{args.markdown}")

    # Console summary
    print(f"\nRaw Corpus 索引完成")
    print(f"  赛事数：{len(aggregates['events'])}")
    print(f"  Archive 数：{aggregates['total_archives']}")
    print(f"  Demo member 数：{aggregates['total_members']}")
    print(f"  未知地图：{aggregates['unknown_map_count']}")
    print(f"  重复候选：{aggregates['duplicate_candidate_count']}")
    print(f"  枚举错误：{aggregates['archives_with_errors']}")
    print(f"  需要 7-Zip：{aggregates['archives_needing_7zip']}")


if __name__ == "__main__":
    main()
