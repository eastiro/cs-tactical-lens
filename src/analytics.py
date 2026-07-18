"""Parser-independent tactical metrics."""
import pandas as pd
from .schema import MatchData, validate_match


def round_progression(data: MatchData) -> pd.DataFrame:
    validate_match(data)
    return data.rounds[["round", "team_a_score", "team_b_score", "winner", "winning_side"]].copy()


def first_kill_summary(data: MatchData) -> pd.DataFrame:
    first = data.kills.loc[data.kills["is_first_kill"]].copy()
    if first.empty:
        return pd.DataFrame(columns=["team", "first_kills", "entry_rate", "median_seconds"])
    summary = (first.groupby("attacker_team", as_index=False).agg(first_kills=("round", "count"), median_seconds=("seconds", "median"))
               .rename(columns={"attacker_team": "team"}))
    summary["entry_rate"] = summary["first_kills"] / max(len(data.rounds), 1)
    return summary.sort_values("first_kills", ascending=False)


def control_snapshot(data: MatchData, team: str, side: str, seconds: int) -> pd.DataFrame:
    """One alive observation per player/round near the requested elapsed second."""
    rows = data.positions.query("team == @team and side == @side").copy()
    if rows.empty:
        return rows
    if "health" in rows:
        rows = rows.loc[rows["health"] > 0]
    if rows.empty:
        return rows
    nearest = rows.assign(distance=(rows["seconds"] - seconds).abs())
    nearest = nearest.loc[nearest.groupby(["round", "player"])["distance"].idxmin()]
    # Do not drag a player's last known position forward from an earlier death
    # or from a round that had already ended before this timestamp.
    return nearest.loc[nearest["distance"] <= 0.75].copy()


def control_profile(data: MatchData, team: str, side: str, seconds: int) -> pd.DataFrame:
    """Area occupancy near a timepoint, not a visibility or territory claim."""
    nearest = control_snapshot(data, team, side, seconds)
    if nearest.empty:
        return pd.DataFrame(columns=["area", "observations", "rounds", "share"])
    out = nearest.groupby("area", as_index=False).agg(
        observations=("player", "size"), rounds=("round", "nunique")
    )
    out["share"] = out["observations"] / out["observations"].sum()
    return out.sort_values("share", ascending=False)


def clutch_summary(data: MatchData) -> pd.DataFrame:
    late = data.kills.loc[data.kills["seconds"] >= 75]
    wins = set(data.rounds.loc[:, ["round", "winner"]].itertuples(index=False, name=None))
    values = []
    for team, frame in late.groupby("attacker_team"):
        attempts = frame["round"].nunique()
        converted = sum((r, team) in wins for r in frame["round"].unique())
        values.append({"team": team, "late_round_attempts": attempts, "converted": converted,
                       "conversion_rate": converted / attempts if attempts else 0})
    return pd.DataFrame(values, columns=["team", "late_round_attempts", "converted", "conversion_rate"])


def build_report(data: MatchData, focus_team: str) -> list[str]:
    first = first_kill_summary(data)
    team_first = first.loc[first["team"] == focus_team]
    control = control_profile(data, focus_team, "T", 50)
    statements = ["这是合成演示数据，只说明报告格式，不代表真实战队。" if data.source_kind == "synthetic" else "结论基于本场 demo；跨场战术习惯需汇总多场比赛验证。"]
    if not team_first.empty:
        row = team_first.iloc[0]
        statements.append(f"{focus_team} 本场拿到 {int(row.first_kills)} 次首杀，首接触中位时间为 {row.median_seconds:.0f} 秒。")
    if not control.empty:
        top = control.iloc[0]
        statements.append(f"在 T 方约 0:50 的采样点，{focus_team} 最常出现于 {top.area} 区（{top.share:.0%} 的位置观测）。")
    return statements
