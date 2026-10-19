"""Multi-match, one-team/one-map opening samples.

This module deliberately stops at observable pre-contact structure.  It does
not infer mid-round intent, call a repeated pattern a set play, or mix teams
and maps into a generic "Mirage tendency".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .awpy_adapter import load_normalized_bundle
from .economy import classify_team_economy
from .schema import MatchData
from .tactics import AREA_GROUP, rounds_for_side

OPENING_COLUMNS = [
    "match_id", "opponent", "event", "date", "round", "side", "sample_second",
    "contact_second", "contact_source", "sample_eligible", "exclusion_reason",
    "economy_scope", "economy_label", "economy_confidence", "economy_reason",
    "A", "B", "MID", "OTHER", "dominant_zone", "formation",
]

# Observation checkpoints after freeze end.  A full-buy can sustain the
# standard 20-second opening lens; low-economy rounds often make meaningful
# contact earlier.  This is an observation rule, never a tactical-intent rule.
ECONOMY_SAMPLE_SECONDS = {
    "full_buy": 20.0,
    "pistol": 15.0,
    "half_buy": 12.0,
    "force_buy": 15.0,
    "eco": 15.0,
}


def sample_second_for_economy(economy_label: object, *, default: float = 20.0) -> float:
    """Return the documented pre-contact checkpoint for one economy label.

    ``mixed`` and ``unknown`` remain in the audited CSV but do not receive a
    special user-facing comparison lens, so they retain the fallback.
    """
    return float(ECONOMY_SAMPLE_SECONDS.get(str(economy_label), default))


@dataclass(frozen=True)
class SeriesMatch:
    match_id: str
    opponent: str
    event: str
    date: str
    bundle_path: Path
    data: MatchData


@dataclass(frozen=True)
class TeamMapSeries:
    team: str
    map_name: str
    season: str
    matches: tuple[SeriesMatch, ...]


def _normalise_map_name(value: object) -> str:
    return str(value).strip().lower()


def _manifest_error(message: str) -> ValueError:
    return ValueError(f"多场清单无效：{message}")


def load_team_map_series(manifest_path: str | Path) -> TeamMapSeries:
    """Load and validate a manifest of normalized bundles for one team/map."""
    path = Path(manifest_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise _manifest_error(f"找不到清单：{path}") from exc
    except json.JSONDecodeError as exc:
        raise _manifest_error(f"JSON 格式错误：{exc.msg}") from exc

    team = str(raw.get("team", "")).strip()
    map_name = _normalise_map_name(raw.get("map", ""))
    if not team:
        raise _manifest_error("缺少 team")
    if not map_name:
        raise _manifest_error("缺少 map")
    entries = raw.get("matches")
    if not isinstance(entries, list) or not entries:
        raise _manifest_error("matches 必须至少包含一场比赛")

    matches: list[SeriesMatch] = []
    match_ids: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise _manifest_error(f"matches[{index}] 必须是对象")
        match_id = str(entry.get("id", "")).strip()
        bundle = str(entry.get("bundle", "")).strip()
        if not match_id or not bundle:
            raise _manifest_error(f"matches[{index}] 缺少 id 或 bundle")
        if match_id in match_ids:
            raise _manifest_error(f"比赛 id 重复：{match_id}")
        match_ids.add(match_id)

        bundle_path = Path(bundle)
        if not bundle_path.is_absolute():
            bundle_path = (path.parent / bundle_path).resolve()
        data = load_normalized_bundle(bundle_path)
        if _normalise_map_name(data.map_name) != map_name:
            raise _manifest_error(
                f"{match_id} 是 {data.map_name}，但清单要求 {map_name}"
            )
        if team not in {data.team_a, data.team_b}:
            raise _manifest_error(
                f"{match_id} 不包含目标队伍 {team}（实际为 {data.team_a} vs {data.team_b}）"
            )
        opponent = data.team_b if data.team_a == team else data.team_a
        declared_opponent = str(entry.get("opponent", "")).strip()
        if declared_opponent and declared_opponent != opponent:
            raise _manifest_error(
                f"{match_id} 的 opponent 写为 {declared_opponent}，但 bundle 中是 {opponent}"
            )
        matches.append(
            SeriesMatch(
                match_id=match_id,
                opponent=opponent,
                event=str(entry.get("event", "")).strip(),
                date=str(entry.get("date", "")).strip(),
                bundle_path=bundle_path,
                data=data,
            )
        )

    return TeamMapSeries(
        team=team,
        map_name=map_name,
        season=str(raw.get("season", "")).strip(),
        matches=tuple(matches),
    )


def _first_contact(data: MatchData, round_num: int) -> tuple[float | None, str]:
    """Return the first opposing-team damage event, falling back to a kill."""
    if not data.damages.empty and {"attacker_team", "victim_team", "seconds"}.issubset(data.damages):
        damages = data.damages.loc[
            (data.damages["round"] == round_num)
            & data.damages["attacker_team"].ne(data.damages["victim_team"])
        ]
        if not damages.empty:
            return float(damages["seconds"].min()), "damage"
    kills = data.kills.loc[
        (data.kills["round"] == round_num)
        & data.kills["attacker_team"].ne(data.kills["victim_team"])
    ]
    if not kills.empty:
        return float(kills["seconds"].min()), "kill_fallback"
    return None, "none"


def _opening_shape(
    data: MatchData, team: str, side: str, round_num: int, sample_second: float
) -> dict[str, object] | None:
    rows = data.positions.loc[
        (data.positions["round"] == round_num)
        & (data.positions["team"] == team)
        & (data.positions["side"] == side)
    ].copy()
    if rows.empty or float(rows["seconds"].max()) < sample_second:
        return None
    rows = rows.loc[rows["seconds"] <= sample_second]
    latest = rows.loc[rows.groupby("player")["seconds"].idxmax()].copy()
    if "health" in latest:
        latest = latest.loc[latest["health"] > 0]
    if latest.empty:
        return None
    latest["zone"] = latest["area"].map(AREA_GROUP).fillna("OTHER")
    counts = latest["zone"].value_counts().reindex(["A", "B", "MID", "OTHER"], fill_value=0)
    maximum = int(counts.max())
    leaders = counts.loc[counts == maximum].index.tolist()
    dominant = leaders[0] if len(leaders) == 1 else "MIXED"
    home = "匪家" if side == "T" else "警家"
    return {
        "A": int(counts["A"]),
        "B": int(counts["B"]),
        "MID": int(counts["MID"]),
        "OTHER": int(counts["OTHER"]),
        "dominant_zone": dominant,
        "formation": (
            f"A{int(counts['A'])}·B{int(counts['B'])}·中{int(counts['MID'])}"
            f"·{home}{int(counts['OTHER'])}"
        ),
    }


def _economy_for_round(data: MatchData, team: str, side: str, round_num: int, pistol_round: bool) -> dict[str, object]:
    """Classify one team/round from its optional freeze-end snapshots."""
    snapshots = data.economy_snapshots
    if snapshots.empty or not {"round", "team"}.issubset(snapshots.columns):
        return {
            "economy_scope": "unclassified",
            "economy_label": "unknown",
            "economy_confidence": "none",
            "economy_reason": "没有冻结结束经济快照",
        }
    rows = snapshots.loc[
        (snapshots["round"] == round_num)
        & snapshots["team"].eq(team)
        & snapshots["side"].eq(side)
    ].copy()
    if rows.empty:
        return {
            "economy_scope": "unclassified",
            "economy_label": "unknown",
            "economy_confidence": "none",
            "economy_reason": "没有匹配到目标队伍/阵营快照",
        }
    result = classify_team_economy(rows, pistol_round=pistol_round)
    return {
        "economy_scope": "freeze_end_snapshot",
        "economy_label": result["label"],
        "economy_confidence": result["confidence"],
        "economy_reason": result["reason"],
    }


def precontact_opening_samples(
    series: TeamMapSeries, *, sample_second: float = 20.0
) -> pd.DataFrame:
    """Extract economy-aware samples only when the checkpoint is before contact.

    Economy is classified only when a verified freeze-end snapshot exists. A
    missing snapshot remains ``unknown``/``unclassified``; consumers must not
    call a mixed sample a complete default profile across buy states.  Known
    labels use ``ECONOMY_SAMPLE_SECONDS``; ``sample_second`` remains the
    conservative fallback for unknown/mixed labels and older non-economy data.
    """
    records: list[dict[str, object]] = []
    for match in series.matches:
        for side in ("T", "CT"):
            side_rounds = rounds_for_side(match.data, series.team, side)
            pistol_round = min(side_rounds) if side_rounds else None
            for round_num in side_rounds:
                contact_second, contact_source = _first_contact(match.data, round_num)
                economy = _economy_for_round(
                    match.data,
                    series.team,
                    side,
                    round_num,
                    pistol_round=round_num == pistol_round,
                )
                observation_second = sample_second_for_economy(
                    economy["economy_label"], default=sample_second
                )
                shape = _opening_shape(
                    match.data, series.team, side, round_num, observation_second
                )
                record: dict[str, object] = {
                    "match_id": match.match_id,
                    "opponent": match.opponent,
                    "event": match.event,
                    "date": match.date,
                    "round": int(round_num),
                    "side": side,
                    "sample_second": observation_second,
                    "contact_second": contact_second,
                    "contact_source": contact_source,
                    "sample_eligible": False,
                    "exclusion_reason": "",
                    **economy,
                    "A": pd.NA,
                    "B": pd.NA,
                    "MID": pd.NA,
                    "OTHER": pd.NA,
                    "dominant_zone": pd.NA,
                    "formation": pd.NA,
                }
                if shape is None:
                    record["exclusion_reason"] = "round_ended_or_missing_position"
                elif contact_second is not None and contact_second <= observation_second:
                    record["exclusion_reason"] = "contact_before_sample"
                else:
                    record.update(shape)
                    record["sample_eligible"] = True
                records.append(record)
    return pd.DataFrame.from_records(records, columns=OPENING_COLUMNS)


def opening_profile(samples: pd.DataFrame) -> pd.DataFrame:
    """Aggregate eligible structures without turning them into a tendency claim."""
    eligible = samples.loc[samples["sample_eligible"]].copy()
    columns = [
        "side", "formation", "sample_count", "match_count", "sample_share",
        "match_ids", "round_evidence",
    ]
    if eligible.empty:
        return pd.DataFrame(columns=columns)
    grouped = eligible.groupby(["side", "formation"], as_index=False).agg(
        sample_count=("round", "size"),
        match_count=("match_id", "nunique"),
        match_ids=("match_id", lambda values: tuple(sorted(set(values)))),
        round_evidence=(
            "round",
            lambda values: tuple(int(value) for value in values),
        ),
    )
    totals = eligible.groupby("side").size().rename("eligible_samples")
    grouped = grouped.merge(totals, on="side", validate="many_to_one")
    grouped["sample_share"] = grouped["sample_count"] / grouped["eligible_samples"]
    return grouped[columns].sort_values(
        ["side", "sample_count", "formation"], ascending=[True, False, True]
    ).reset_index(drop=True)


def series_evidence_summary(
    samples: pd.DataFrame, profile: pd.DataFrame, side: str
) -> dict[str, object]:
    """Summarise the evidence scope for one side without inferring intent."""
    side_samples = samples.loc[samples["side"] == side].copy()
    eligible = side_samples.loc[side_samples["sample_eligible"]].copy()
    side_profile = profile.loc[profile["side"] == side].copy()
    contact = pd.to_numeric(eligible["contact_second"], errors="coerce").dropna()

    top = side_profile.sort_values(
        ["sample_count", "match_count", "formation"],
        ascending=[False, False, True],
    ).head(1)
    top_row = top.iloc[0] if not top.empty else None
    return {
        "side": side,
        "total_rounds": int(len(side_samples)),
        "eligible_samples": int(len(eligible)),
        "coverage_matches": int(eligible["match_id"].nunique()),
        "unique_formations": int(eligible["formation"].nunique()),
        "repeated_3_matches": int((side_profile["match_count"] >= 3).sum()),
        "median_contact_second": float(contact.median()) if not contact.empty else None,
        "q25_contact_second": float(contact.quantile(0.25)) if not contact.empty else None,
        "q75_contact_second": float(contact.quantile(0.75)) if not contact.empty else None,
        "top_formation": str(top_row["formation"]) if top_row is not None else None,
        "top_formation_count": int(top_row["sample_count"]) if top_row is not None else 0,
        "top_formation_matches": int(top_row["match_count"]) if top_row is not None else 0,
        "top_formation_share": float(top_row["sample_share"]) if top_row is not None else 0.0,
    }
