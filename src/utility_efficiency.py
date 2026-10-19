"""Narrow, directly recorded utility events for one imported match.

Only HE/fire enemy damage and flash assists are treated as measurable here.
Smoke vision denial, space gained and enemies forced off angles are not present
in the normalized demo events and therefore are deliberately not estimated.
"""

from __future__ import annotations

import pandas as pd

from .schema import MatchData

UTILITY_ALIASES = {
    "smoke": "smoke",
    "smokegrenade": "smoke",
    "flash": "flash",
    "flashbang": "flash",
    "he": "he",
    "hegrenade": "he",
    "molotov": "molotov",
    "inferno": "molotov",
    "decoy": "decoy",
}


def _canonical_utility(value: object) -> str:
    key = str(value).lower().replace("_", "").replace(" ", "")
    return UTILITY_ALIASES.get(key, str(value).lower())


def _round_team_sides(data: MatchData) -> dict[tuple[int, str], str]:
    rows = data.positions.dropna(subset=["round", "team", "side"])
    grouped = rows.groupby(["round", "team"])["side"].agg(lambda values: values.mode().iat[0])
    return {(int(round_num), str(team)): str(side).upper() for (round_num, team), side in grouped.items()}


def utility_outcomes(data: MatchData) -> pd.DataFrame:
    """Return one auditable direct-event row for every grenade throw."""
    if data.grenades.empty:
        return pd.DataFrame()

    sides = _round_team_sides(data)
    records: list[dict[str, object]] = []
    for grenade_id, grenade in data.grenades.reset_index(drop=True).iterrows():
        round_num = int(grenade["round"])
        team = str(grenade["team"])
        thrower = str(grenade["thrower"])
        utility_type = _canonical_utility(grenade["grenade_type"])
        throw_second = float(grenade["seconds"])
        land_value = grenade.get("land_seconds", throw_second)
        land_second = throw_second if pd.isna(land_value) else float(land_value)
        end_value = grenade.get("effect_end_seconds", pd.NA)
        effect_end = None if pd.isna(end_value) else float(end_value)

        direct_damage = 0.0
        if not data.damages.empty and utility_type in {"he", "molotov"}:
            damage_rows = data.damages.loc[
                (data.damages["round"] == round_num)
                & (data.damages["attacker"] == thrower)
                & (data.damages["attacker_team"] == team)
                & (data.damages["victim_team"] != team)
            ].copy()
            weapons = damage_rows["weapon"].astype(str).str.lower()
            if utility_type == "he":
                damage_rows = damage_rows.loc[
                    weapons.eq("hegrenade")
                    & damage_rows["seconds"].between(land_second - 0.35, land_second + 0.35)
                ]
            else:
                damage_end = effect_end if effect_end is not None else land_second + 7.5
                damage_rows = damage_rows.loc[
                    weapons.isin({"inferno", "molotov"})
                    & damage_rows["seconds"].between(land_second - 0.15, damage_end + 0.15)
                ]
            direct_damage = float(damage_rows["damage_health"].sum())

        records.append(
            {
                "grenade_id": int(grenade_id),
                "round": round_num,
                "side": sides.get((round_num, team), ""),
                "team": team,
                "thrower": thrower,
                "grenade_type": utility_type,
                "seconds": throw_second,
                "land_seconds": land_second,
                "damage_health": direct_damage,
                "flash_assists": 0,
            }
        )

    outcomes = pd.DataFrame.from_records(records)
    if "assisted_flash" not in data.kills or "assister" not in data.kills:
        return outcomes

    flash_assists = data.kills.loc[data.kills["assisted_flash"].eq(True)]
    for kill in flash_assists.itertuples():
        candidates = outcomes.loc[
            (outcomes["round"] == int(kill.round))
            & (outcomes["grenade_type"] == "flash")
            & (outcomes["thrower"] == str(kill.assister))
            & outcomes["land_seconds"].le(float(kill.seconds))
            & outcomes["land_seconds"].ge(float(kill.seconds) - 5.0)
        ]
        if candidates.empty:
            continue
        grenade_id = int(candidates.sort_values("land_seconds").iloc[-1]["grenade_id"])
        outcomes.loc[outcomes["grenade_id"] == grenade_id, "flash_assists"] += 1
    return outcomes


def utility_efficiency_summary(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Aggregate only directly recorded damage/assist signals."""
    columns = [
        "team", "side", "grenade_type", "throws", "direct_event_throws",
        "damage_health", "flash_assists",
    ]
    if outcomes.empty:
        return pd.DataFrame(columns=columns)
    direct_types = outcomes.loc[
        outcomes["grenade_type"].isin({"he", "molotov", "flash"})
    ].copy()
    if direct_types.empty:
        return pd.DataFrame(columns=columns)
    direct_types["has_direct_event"] = (
        direct_types["damage_health"].gt(0) | direct_types["flash_assists"].gt(0)
    )
    summary = direct_types.groupby(["team", "side", "grenade_type"], as_index=False).agg(
        throws=("grenade_id", "size"),
        direct_event_throws=("has_direct_event", "sum"),
        damage_health=("damage_health", "sum"),
        flash_assists=("flash_assists", "sum"),
    )
    return summary[columns].sort_values(
        ["team", "side", "direct_event_throws", "throws"],
        ascending=[True, True, False, False],
    )
