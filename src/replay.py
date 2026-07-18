"""Round-level selections used by the tactical replay surface."""

from __future__ import annotations

import pandas as pd

from .schema import MatchData


UTILITY_LABELS = {
    "smoke": "烟雾弹",
    "flash": "闪光弹",
    "molotov": "燃烧弹",
    "he": "高爆手雷",
    "decoy": "诱饵弹",
}


def position_snapshot(data: MatchData, round_num: int, second: float) -> pd.DataFrame:
    rows = data.positions.loc[
        (data.positions["round"] == round_num) & (data.positions["seconds"] <= second)
    ].copy()
    if rows.empty:
        return rows
    snapshot = rows.loc[rows.groupby("player")["seconds"].idxmax()].copy()
    if "health" in snapshot:
        snapshot = snapshot.loc[snapshot["health"] > 0]
    return snapshot


def movement_trails(data: MatchData, round_num: int, second: float, *, lookback: float = 8.0) -> pd.DataFrame:
    rows = data.positions.loc[
        (data.positions["round"] == round_num)
        & data.positions["seconds"].between(max(0, second - lookback), second)
    ].copy()
    if rows.empty:
        return rows
    # One point per roughly half-second is enough for a readable trail.
    rows["half_second"] = (rows["seconds"] * 2).round().astype(int)
    return rows.sort_values("seconds").drop_duplicates(["player", "half_second"], keep="last")


def round_kills(data: MatchData, round_num: int, second: float | None = None) -> pd.DataFrame:
    rows = data.kills.loc[data.kills["round"] == round_num].sort_values("seconds").copy()
    return rows if second is None else rows.loc[rows["seconds"] <= second]


def round_utility(data: MatchData, round_num: int, second: float | None = None) -> pd.DataFrame:
    rows = data.grenades.loc[data.grenades["round"] == round_num].sort_values("seconds").copy()
    if second is not None:
        rows = rows.loc[rows["seconds"] <= second]
    rows["utility_label"] = rows["grenade_type"].map(UTILITY_LABELS).fillna(rows["grenade_type"])
    return rows


def entry_conversion_summary(data: MatchData) -> pd.DataFrame:
    firsts = data.kills.loc[data.kills["is_first_kill"], ["round", "attacker_team"]].copy()
    firsts = firsts.merge(data.rounds[["round", "winner"]], on="round", how="left", validate="one_to_one")
    firsts["converted"] = firsts["attacker_team"] == firsts["winner"]
    result = firsts.groupby("attacker_team", as_index=False).agg(
        first_kills=("round", "count"), converted=("converted", "sum")
    ).rename(columns={"attacker_team": "team"})
    result["conversion_rate"] = result["converted"] / result["first_kills"]
    return result


def score_after_round(data: MatchData, round_num: int) -> tuple[int, int]:
    row = data.rounds.loc[data.rounds["round"] == round_num].iloc[0]
    return int(row.team_a_score), int(row.team_b_score)
