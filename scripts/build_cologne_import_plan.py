r"""Build the IEM Cologne Major 2026 import plan.

Produces a team–map coverage matrix and recommends a first cohort of
match–map combinations to parse from **stage-3 + playoffs** only.

Usage::

    python scripts/build_cologne_import_plan.py
        --registry data/registry/iem-cologne-major-2026-match-registry.json
        --output data/registry/iem-cologne-major-2026-import-plan.json
        --report reports/iem-cologne-major-2026-import-plan.md

"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _deduplicate_members(
    members: list[dict],
) -> list[dict]:
    """Deduplicate members by map name (handles p1/p2 splits)."""
    seen_maps: set[str] = set()
    deduped: list[dict] = []
    for m in members:
        map_name = m["map"]
        if map_name not in seen_maps:
            seen_maps.add(map_name)
            deduped.append(m)
    return deduped


def _build_team_map_coverage(
    records: list[dict],
) -> dict:
    """Build team–map coverage from registered records.

    Returns
        - team_map_rows: list of {team, map, distinct_match_count, match_ids,
          stage_breakdown}
        - per_map_cross: dict[map] -> {teams_with_5+, teams_with_3_4, ...}
    """
    # (team_slug, map) -> {match_ids, stages_count}
    coverage: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"match_ids": set(), "stages": defaultdict(int)}
    )

    for rec in records:
        match_id = rec["match_id"]
        stage = rec["stage"]
        teams = rec["teams"]
        deduped_maps = _deduplicate_members(rec["members"])

        for m in deduped_maps:
            map_name = m["map"]
            for team in teams:
                key = (team, map_name)
                coverage[key]["match_ids"].add(match_id)
                coverage[key]["stages"][stage] += 1

    rows: list[dict] = []
    for (team, map_name), data in sorted(coverage.items()):
        rows.append({
            "team": team,
            "map": map_name,
            "distinct_match_count": len(data["match_ids"]),
            "match_ids": sorted(data["match_ids"]),
            "stage_breakdown": dict(data["stages"]),
        })

    # Per-map cross-team comparison
    per_map: dict[str, dict] = {}
    for row in rows:
        m = row["map"]
        if m not in per_map:
            per_map[m] = {"teams_and_counts": []}
        per_map[m]["teams_and_counts"].append({
            "team": row["team"],
            "matches": row["distinct_match_count"],
        })

    # Add threshold annotations
    for m, data in per_map.items():
        teams_5 = [t for t in data["teams_and_counts"] if t["matches"] >= 5]
        teams_3 = [t for t in data["teams_and_counts"] if 3 <= t["matches"] < 5]
        data["teams_with_5plus"] = teams_5
        data["teams_with_3_4"] = teams_3

    return {"rows": rows, "per_map_cross": per_map}


def _recommend_cohort(
    team_map: dict,
    stage3_records: list[dict],
) -> list[dict]:
    """Recommend first cohort from stage-3 + playoffs only."""
    recommendations: list[dict] = []
    per_map = team_map["per_map_cross"]

    # Only consider maps where at least 2 teams have >= 5 matches
    candidate_maps = []
    exploratory_maps = []

    for map_name, data in sorted(per_map.items()):
        teams_5 = data.get("teams_with_5plus", [])
        teams_3 = data.get("teams_with_3_4", [])

        if len(teams_5) >= 2:
            candidate_maps.append((map_name, teams_5, "standard"))
        elif len(teams_5) + len(teams_3) >= 2:
            # At least 2 teams with >= 3 matches
            eligible = teams_5 + teams_3
            if len(eligible) >= 2:
                exploratory_maps.append((map_name, eligible, "exploratory"))

    def _build_rec(map_name, teams_list, tier, reason_note=""):
        match_ids = set()
        for t in teams_list:
            row = next(
                (r for r in team_map["rows"]
                 if r["team"] == t["team"] and r["map"] == map_name),
                None,
            )
            if row:
                match_ids.update(row["match_ids"])

        teams_detail = [
            {"team": t["team"], "candidate_matches": t["matches"]}
            for t in teams_list
        ]
        return {
            "map": map_name,
            "tier": tier,
            "teams": teams_detail,
            "total_unique_matches": len(match_ids),
            "related_match_ids": sorted(match_ids),
            "rationale": (
                f"{' 和 '.join(t['team'] for t in teams_detail[:2])}"
                f" 在 {map_name} 各有 {teams_detail[0]['candidate_matches']}"
                f" 和 {teams_detail[1]['candidate_matches']} 场候选比赛，"
                f"可支持同地图跨队伍对比。" + (f" {reason_note}" if reason_note else "")
            ),
            "limitations": (
                "基于 raw archive 文件名识别的地图标签；对手分布和时间段未经验证；"
                "实际可用样本可能在解析后减少（如 .dem 损坏、阵营不均衡）。"
            ),
        }

    for map_name, teams_5, _ in candidate_maps:
        recommendations.append(
            _build_rec(map_name, teams_5, "standard")
        )

    for map_name, eligible, _ in exploratory_maps:
        recommendations.append(
            _build_rec(map_name, eligible, "exploratory",
                       reason_note="暂无双队均达到 5 场候选，当前为 exploratory 推荐，需在解析后重新评估样本充足性。")
        )

    # Limit to top 5 recommendations
    return recommendations[:5]


def _build_plan(registry: dict) -> dict:
    """Build the full import plan from the registry."""
    # Only registered records
    registered = [rec for rec in registry["records"] if rec["status"] == "registered"]
    missing_ids = [rec["match_id"] for rec in registry["records"] if rec["status"] == "missing_archive"]

    # Compute deduplicated member counts
    total_raw_members = sum(len(rec["members"]) for rec in registered)
    total_dedup_samples = sum(
        len(_deduplicate_members(rec["members"])) for rec in registered
    )

    # Team-map coverage (all stages)
    all_coverage = _build_team_map_coverage(registered)

    # Stage-3 + playoffs only
    stage3_playoff_records = [
        rec for rec in registered
        if rec["stage"] in ("stage-3", "playoffs")
    ]
    s3p_coverage = _build_team_map_coverage(stage3_playoff_records)

    # Recommended first cohort
    recommendations = _recommend_cohort(s3p_coverage, stage3_playoff_records)

    # Stage breakdown of team-map candidates
    stage_breakdown: dict[str, dict] = {}
    for stage_name in ("stage-2", "stage-3", "playoffs"):
        stage_recs = [rec for rec in registered if rec["stage"] == stage_name]
        members = sum(len(_deduplicate_members(rec["members"])) for rec in stage_recs)
        stage_breakdown[stage_name] = {
            "registered_matches": len(stage_recs),
            "dedup_map_samples": members,
        }

    summary = {
        "total_registered_matches": len(registered),
        "total_missing_matches": len(missing_ids),
        "missing_match_ids": sorted(missing_ids),
        "total_raw_members": total_raw_members,
        "total_dedup_map_samples": total_dedup_samples,
        "stage_breakdown": stage_breakdown,
        "note": "maps miss_dedup_count 已按 (match_id, map) 去重（处理 p1/p2 拆分）。"
        "Stage 2 不应纳入首批解析；第一批仅从 stage-3 + playoffs 选取。",
    }

    return {
        "event": "IEM Cologne Major 2026",
        "source_registry": "data/registry/iem-cologne-major-2026-match-registry.json",
        "scope": "registered records only; raw candidate coverage, not parsed analysis data",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "all_registered_coverage": {
            "team_map_rows": all_coverage["rows"],
            "per_map_cross": all_coverage["per_map_cross"],
        },
        "stage3_playoffs_coverage": {
            "team_map_rows": s3p_coverage["rows"],
            "per_map_cross": s3p_coverage["per_map_cross"],
        },
        "recommended_first_cohort": recommendations,
    }


def _build_md_report(plan: dict) -> str:
    """Render a human-readable Markdown import-plan report in Chinese."""
    lines: list[str] = []
    s = plan["summary"]

    lines.append("# IEM Cologne Major 2026 — 解析批次规划\n")
    lines.append(f"> 生成时间：{plan['generated_at']}\n")
    lines.append(
        "本规划基于注册表 `iem-cologne-major-2026-match-registry.json` 生成。"
        "**所有数字均为 raw 候选覆盖，不代表已解析或已验证的数据。**\n"
    )

    # ── Overview ──
    lines.append("## 总览\n")
    lines.append(f"- 注册比赛：**{s['total_registered_matches']}** 场")
    lines.append(f"- 缺失比赛：**{s['total_missing_matches']}** 场（Astralis vs TYLOO、Legacy vs TYLOO）")
    lines.append(f"- Raw demo member：**{s['total_raw_members']}** 个")
    lines.append(f"- 去重后待解析地图样本：**{s['total_dedup_map_samples']}** 个")
    lines.append("- 缺失比赛不阻塞当前第一批，待后续手动下载补充即可。\n")

    lines.append("### 分阶段明细\n")
    lines.append("| 阶段 | 注册比赛 | 去重地图样本 |")
    lines.append("|------|---------|-------------|")
    for stage in ("stage-2", "stage-3", "playoffs"):
        sb = s["stage_breakdown"].get(stage, {})
        lines.append(
            f"| {stage} | {sb.get('registered_matches', 0)} | {sb.get('dedup_map_samples', 0)} |"
        )
    lines.append("")

    # ── All registered coverage ──
    lines.append("## 全量覆盖（Stage 2 + Stage 3 + Playoffs）\n")
    _add_team_map_section(lines, plan["all_registered_coverage"], "全量")

    # ── Stage-3 + Playoffs coverage ──
    lines.append("## Stage 3 + Playoffs 覆盖（首批候选范围）\n")
    lines.append(
        "Stage 2 不纳入首批解析，因此以下只列出 **stage-3 + playoffs** 的覆盖。\n"
    )
    _add_team_map_section(lines, plan["stage3_playoffs_coverage"], "s3p")

    # ── Recommended first cohort ──
    lines.append("## 推荐第一批解析\n")
    recs = plan.get("recommended_first_cohort", [])
    if not recs:
        lines.append(
            "暂无双队在同一地图达到最低候选门槛（>= 5 场），"
            "也无符合条件的 exploratory 推荐。建议先在 stage-3 + playoffs 中补充更多比赛。\n"
        )
    else:
        for i, rec in enumerate(recs, 1):
            tier_label = "标准推荐" if rec["tier"] == "standard" else "Exploratory 推荐"
            lines.append(f"### {i}. {rec['map']} — {tier_label}\n")
            lines.append(f"- **地图**：{rec['map']}")
            lines.append("- **队伍**：")
            for t in rec["teams"]:
                lines.append(f"  - {t['team']}：{t['candidate_matches']} 场候选")
            lines.append(f"- **去重比赛数**：{rec['total_unique_matches']}")
            lines.append(f"- **涉及比赛**：{', '.join(rec['related_match_ids'])}")
            lines.append(f"- **推荐理由**：{rec['rationale']}")
            lines.append(f"- **局限性**：{rec['limitations']}")
            lines.append("")

    # ── Boundary ──
    lines.append("---\n")
    lines.append(
        "**边界声明**：本规划仅基于注册表中的 archive 文件名和目录结构计算 raw 候选覆盖。"
        "所有未解析 demo 内容，未验证队伍阵容或比赛事实。"
        "实际可导入样本可能在解析后因 .dem 损坏、阵容变动等原因减少。\n"
    )

    return "\n".join(lines)


def _add_team_map_section(
    lines: list[str],
    coverage: dict,
    prefix: str,
) -> None:
    """Add a team-map coverage table section."""
    rows = coverage.get("team_map_rows", [])
    lines.append("### 队伍 × 地图 覆盖表\n")
    lines.append("| 队伍 | 地图 | 比赛数 | 阶段分布 |")
    lines.append("|------|------|--------|---------|")
    for row in rows:
        stage_str = ", ".join(
            f"{s}:{c}" for s, c in sorted(row["stage_breakdown"].items())
        )
        lines.append(
            f"| {row['team']} | {row['map']} | {row['distinct_match_count']} | {stage_str} |"
        )
    lines.append("")

    # Cross-map comparison
    per_map = coverage.get("per_map_cross", {})
    lines.append("### 各地图跨队伍对比\n")
    lines.append("| 地图 | 达 5+ 场队伍 | 达 3–4 场队伍 |")
    lines.append("|------|------------|-------------|")
    for map_name, data in sorted(per_map.items()):
        teams_5 = data.get("teams_with_5plus", [])
        teams_3 = data.get("teams_with_3_4", [])
        t5_str = ", ".join(f"{t['team']}({t['matches']})" for t in teams_5) if teams_5 else "—"
        t3_str = ", ".join(f"{t['team']}({t['matches']})" for t in teams_3) if teams_3 else "—"
        lines.append(f"| {map_name} | {t5_str} | {t3_str} |")
    lines.append("")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IEM Cologne Major 2026 解析批次规划——"
        "从注册表生成 team-map 覆盖矩阵和推荐解析队列"
    )
    parser.add_argument(
        "--registry", type=Path, required=True,
        help="iem-cologne-major-2026-match-registry.json 路径",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="规划 JSON 输出路径",
    )
    parser.add_argument(
        "--report", type=Path, required=True,
        help="Markdown 报告输出路径",
    )
    args = parser.parse_args()

    if not args.registry.is_file():
        parser.error(f"找不到注册表文件：{args.registry}")

    registry = _load_registry(args.registry)
    plan = _build_plan(registry)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"规划 JSON：{args.output}")

    md = _build_md_report(plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(md, encoding="utf-8")
    print(f"规划报告：{args.report}")

    s = plan["summary"]
    print("\nIEM Cologne Major 2026 解析规划完成")
    print(f"  注册比赛：{s['total_registered_matches']}")
    print(f"  去重地图样本：{s['total_dedup_map_samples']}")
    print(f"  推荐批次：{len(plan['recommended_first_cohort'])} 个")


if __name__ == "__main__":
    main()
