"""Print a read-only readiness report for team-map research series."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.coverage_audit import coverage_rows, unassigned_bundles


def build_report(series_root: Path, processed_root: Path, threshold: int) -> dict[str, object]:
    rows = coverage_rows(series_root, threshold=threshold)
    return {
        "threshold_matches": threshold,
        "complete_series": [
            {
                "profile_id": row.profile_id,
                "team": row.team,
                "map": row.map_name,
                "season": row.season,
                "complete_matches": row.complete_matches,
                "eligible_samples": row.eligible_samples,
                "pairable": row.pairable,
                "matches_to_threshold": row.matches_to_threshold,
            }
            for row in rows
        ],
        "unassigned_parsed_bundles": [str(path) for path in unassigned_bundles(series_root, processed_root)],
        "boundary": "仅盘点本地完整 series 与已解析 bundle；不下载、不解析、不修改数据。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="审计本地 team-map series 的可比较覆盖度")
    parser.add_argument("--series-root", type=Path, default=Path("data/series"))
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--threshold", type=int, default=5)
    parser.add_argument("--output", type=Path, help="可选 JSON 报告路径")
    args = parser.parse_args()
    if args.threshold < 1:
        parser.error("--threshold 必须至少为 1")
    report = build_report(args.series_root, args.processed_root, args.threshold)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
