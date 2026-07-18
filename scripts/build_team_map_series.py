"""Build auditable, pre-contact samples for one team on one map.

Example:
    python scripts/build_team_map_series.py data/series/furia-mirage.json --output data/series/furia-mirage
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.team_map_series import (
    ECONOMY_SAMPLE_SECONDS,
    load_team_map_series,
    opening_profile,
    precontact_opening_samples,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="为同队同图多场 Demo 生成接触前站位样本，不判断既定战术。"
    )
    parser.add_argument("manifest", type=Path, help="一支队伍、一张地图的 JSON 清单")
    parser.add_argument("--output", type=Path, required=True, help="输出目录")
    parser.add_argument(
        "--sample-second", type=float, default=20.0,
        help="unknown/mixed 或旧 series 的保守观察秒数，默认 20；已识别经济局使用分层秒数",
    )
    args = parser.parse_args()
    if args.sample_second <= 0:
        parser.error("--sample-second 必须大于 0")

    series = load_team_map_series(args.manifest)
    samples = precontact_opening_samples(series, sample_second=args.sample_second)
    profile = opening_profile(samples)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    samples.to_csv(output / "precontact_opening_samples.csv", index=False)
    profile.to_csv(output / "precontact_opening_profile.csv", index=False)
    economy_ready = samples["economy_scope"].eq("freeze_end_snapshot").any()
    economy_counts = {
        str(label): int(count)
        for label, count in samples.loc[samples["sample_eligible"], "economy_label"].value_counts().items()
    }
    metadata = {
        "team": series.team,
        "map": series.map_name,
        "season": series.season,
        "match_count": len(series.matches),
        "sample_second": args.sample_second,
        "economy_sample_seconds": ECONOMY_SAMPLE_SECONDS,
        "total_round_samples": len(samples),
        "eligible_precontact_samples": int(samples["sample_eligible"].sum()),
        "economy_scope": "freeze_end_snapshot" if economy_ready else "unclassified",
        "economy_label_counts": economy_counts,
        "boundary": (
            "Only samples before the first observed opposing-team damage (or first kill "
            "when damage events are unavailable). Known economy labels use documented "
            "observation checkpoints; this does not identify a set play or a team tendency. "
            "Economy labels describe freeze-end loadout evidence only."
        ),
    }
    (output / "series_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已生成：{output}")
    print(
        f"{series.team} · {series.map_name} · {len(series.matches)} 场 · "
        f"接触前有效样本 {int(samples['sample_eligible'].sum())}/{len(samples)}"
    )
    print("注意：经济标签描述冻结结束装备证据，不等于购买意图或默认战术。")


if __name__ == "__main__":
    main()
