"""Descriptive comparison helpers for two same-map team series.

The comparison deliberately stays at the same evidence boundary as
``team_map_series``: only eligible samples taken before first contact are
compared.  It does not estimate win strength, infer calls, or turn a repeated
formation into a default tactic.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


PROFILE_COLUMNS = [
    "formation",
    "sample_count",
    "match_count",
    "sample_share",
    "median_contact_second",
    "opponents",
]


def _eligible(samples: pd.DataFrame, side: str, economy: str | None = None) -> pd.DataFrame:
    """Return a defensive copy of one side's eligible samples."""
    if samples.empty:
        return samples.copy()
    result = samples.loc[samples["side"].eq(side)].copy()
    eligible = result["sample_eligible"]
    if eligible.dtype != bool:
        eligible = eligible.astype(str).str.strip().str.lower().eq("true")
    result = result.loc[eligible & result["formation"].notna()].copy()
    if economy and economy not in {"全部经济状态", "all"} and "economy_label" in result:
        result = result.loc[result["economy_label"].eq(economy)]
    return result


def opening_profile_for_comparison(
    samples: pd.DataFrame, side: str, economy: str | None = None
) -> pd.DataFrame:
    """Aggregate one team's eligible opening structures for one side."""
    eligible = _eligible(samples, side, economy)
    if eligible.empty:
        return pd.DataFrame(columns=PROFILE_COLUMNS)

    contact = pd.to_numeric(eligible["contact_second"], errors="coerce")
    eligible = eligible.assign(_contact_second=contact)
    profile = (
        eligible.groupby("formation", as_index=False)
        .agg(
            sample_count=("round", "size"),
            match_count=("match_id", "nunique"),
            median_contact_second=("_contact_second", "median"),
            opponents=("opponent", lambda values: tuple(sorted(set(values)))),
        )
    )
    profile["sample_share"] = profile["sample_count"] / len(eligible)
    return profile[PROFILE_COLUMNS].sort_values(
        ["sample_count", "match_count", "formation"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def compare_opening_profiles(
    team_samples: dict[str, pd.DataFrame], side: str, economy: str | None = None
) -> pd.DataFrame:
    """Build a union table comparing the same side across two teams.

    ``team_samples`` is intentionally a mapping so the view can add another
    team later without changing the evidence definition.  The current V3 UI
    passes exactly Falcons and Spirit.
    """
    profiles: dict[str, pd.DataFrame] = {
        team: opening_profile_for_comparison(samples, side, economy)
        for team, samples in team_samples.items()
    }
    names = list(profiles)
    if not names:
        return pd.DataFrame(columns=["formation"])

    union = sorted(
        {
            str(formation)
            for profile in profiles.values()
            for formation in profile["formation"].dropna().tolist()
        }
    )
    if not union:
        return pd.DataFrame(columns=["formation"])
    result = pd.DataFrame({"formation": union})
    for team in names:
        profile = profiles[team].copy()
        prefix = team.lower().replace(" ", "_")
        profile = profile.rename(
            columns={
                "sample_count": f"{prefix}_sample_count",
                "match_count": f"{prefix}_match_count",
                "sample_share": f"{prefix}_sample_share",
                "median_contact_second": f"{prefix}_median_contact_second",
                "opponents": f"{prefix}_opponents",
            }
        )
        result = result.merge(profile, on="formation", how="left")
        for suffix in ("sample_count", "match_count"):
            column = f"{prefix}_{suffix}"
            result[column] = result[column].fillna(0).astype(int)
        result[f"{prefix}_sample_share"] = result[f"{prefix}_sample_share"].fillna(0.0)
        result[f"{prefix}_median_contact_second"] = pd.to_numeric(
            result[f"{prefix}_median_contact_second"], errors="coerce"
        )
        result[f"{prefix}_opponents"] = result[f"{prefix}_opponents"].map(
            lambda value: tuple(value) if isinstance(value, Iterable) and not isinstance(value, str) else tuple()
        )

    if len(names) >= 2:
        left = names[0].lower().replace(" ", "_")
        right = names[1].lower().replace(" ", "_")
        result["sample_count_delta"] = (
            result[f"{left}_sample_count"] - result[f"{right}_sample_count"]
        )
        result["share_delta"] = (
            result[f"{left}_sample_share"] - result[f"{right}_sample_share"]
        )
    return result.sort_values(
        [f"{names[0].lower().replace(' ', '_')}_sample_count", "formation"],
        ascending=[False, True],
    ).reset_index(drop=True)


def comparison_evidence(
    team_samples: dict[str, pd.DataFrame],
    side: str,
    *,
    formation: str | None = None,
    team: str | None = None,
    economy: str | None = None,
    limit: int = 40,
) -> pd.DataFrame:
    """Return concrete match/round evidence rows for the comparison table."""
    frames: list[pd.DataFrame] = []
    for team_name, samples in team_samples.items():
        if team and team != "两队" and team_name != team:
            continue
        eligible = _eligible(samples, side, economy)
        if formation and formation != "全部结构":
            eligible = eligible.loc[eligible["formation"].eq(formation)]
        if eligible.empty:
            continue
        evidence = eligible.assign(team=team_name).copy()
        frames.append(evidence)

    columns = [
        "team",
        "event",
        "opponent",
        "date",
        "round",
        "side",
        "formation",
        "contact_second",
        "match_id",
    ]
    if not frames:
        return pd.DataFrame(columns=columns)
    result = pd.concat(frames, ignore_index=True)
    result["contact_second"] = pd.to_numeric(result["contact_second"], errors="coerce")
    result = result.sort_values(["date", "team", "match_id", "round"])
    return result.head(max(1, int(limit)))[columns].reset_index(drop=True)
