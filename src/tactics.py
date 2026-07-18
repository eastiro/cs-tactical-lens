"""Evidence-backed single-match tactical patterns.

The functions in this module deliberately describe only the imported match.  A
finding always carries the rounds and timestamps a reviewer can reopen on the
radar; it is never promoted to a long-term team tendency here.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .schema import MatchData


AREA_GROUP = {
    # A approach / site
    "BombsiteA": "A",
    "TRamp": "A",
    "PalaceAlley": "A",
    "PalaceInterior": "A",
    "Scaffolding": "A",
    "Stairs": "A",
    "Jungle": "A",
    # B approach / site
    "BombsiteB": "B",
    "Apartments": "B",
    "BackAlley": "B",
    "SideAlley": "B",
    "Shop": "B",
    "House": "B",
    "Truck": "B",
    # Mid control
    "Middle": "MID",
    "TopofMid": "MID",
    "Connector": "MID",
    "Catwalk": "MID",
    "Underpass": "MID",
    "Ladder": "MID",
    "SnipersNest": "MID",
}

ZONE_LABEL = {"A": "A 区", "B": "B 区", "MID": "中路", "MIXED": "分散站位", "OTHER": "出生点附近"}

AREA_LABEL = {
    "Apartments": "B 二楼",
    "BackAlley": "B 二楼后段",
    "BombsiteA": "A 包点",
    "BombsiteB": "B 包点",
    "CTSpawn": "警家",
    "Catwalk": "B 小",
    "Connector": "拱门",
    "House": "匪二楼",
    # Jungle is the A-site area between Stairs and Sniper's Nest/Window;
    # it is not CT Spawn (警家) and should not be rendered as "VIP 下".
    "Jungle": "丛林（Jungle）",
    "Ladder": "黑屋",
    "Middle": "中路",
    "PalaceAlley": "A2 入口",
    "PalaceInterior": "A2（二楼）",
    "Scaffolding": "A2 平台",
    "Shop": "超市",
    "SideAlley": "B 二楼外",
    # Keep the parser's canonical name visible so the local "VIP" nickname
    # does not get confused with the whole Mid area.
    "SnipersNest": "狙击房（Sniper's Nest，俗称 VIP）",
    "Stairs": "跳台",
    "TRamp": "A1",
    "TSpawn": "匪家",
    "TopofMid": "中远",
    "Truck": "白车",
    "Underpass": "下水道",
}


@dataclass(frozen=True)
class TacticalEvidence:
    round_num: int
    second: float
    label: str


@dataclass(frozen=True)
class TacticalFinding:
    kind: str
    title: str
    summary: str
    sample_size: int
    evidence: tuple[TacticalEvidence, ...]


def _round_side_table(data: MatchData) -> pd.DataFrame:
    rows = data.positions.dropna(subset=["team", "side"])
    return (
        rows.groupby(["round", "team"], as_index=False)["side"]
        .agg(lambda values: values.mode().iat[0])
    )


def rounds_for_side(data: MatchData, team: str, side: str) -> list[int]:
    assignments = _round_side_table(data)
    return assignments.loc[
        (assignments["team"] == team) & (assignments["side"] == side.upper()), "round"
    ].astype(int).tolist()


def grenades_for_side(data: MatchData, team: str, side: str) -> pd.DataFrame:
    """Return only the team's grenades from rounds played on the requested side."""
    side_rounds = rounds_for_side(data, team, side)
    return data.grenades.loc[
        (data.grenades["team"] == team) & data.grenades["round"].isin(side_rounds)
    ].copy()


def position_shapes(data: MatchData, team: str, side: str, sample_second: float) -> pd.DataFrame:
    """One auditable team shape per round at an elapsed-time sample."""
    round_numbers = rounds_for_side(data, team, side)
    rows = data.positions.loc[
        (data.positions["team"] == team)
        & (data.positions["side"] == side.upper())
        & (data.positions["round"].isin(round_numbers))
    ].copy()
    if rows.empty:
        return pd.DataFrame(columns=["round", "seconds", "A", "B", "MID", "OTHER", "dominant_zone"])

    # Do not pretend a round has a 40-second shape when it ended at 25 seconds.
    eligible = rows.groupby("round")["seconds"].max().loc[lambda values: values >= sample_second].index
    rows = rows.loc[(rows["round"].isin(eligible)) & (rows["seconds"] <= sample_second)]
    if rows.empty:
        return pd.DataFrame(columns=["round", "seconds", "A", "B", "MID", "OTHER", "dominant_zone"])

    latest = rows.loc[rows.groupby(["round", "player"])["seconds"].idxmax()].copy()
    if "health" in latest:
        latest = latest.loc[latest["health"] > 0]
    latest["zone"] = latest["area"].map(AREA_GROUP).fillna("OTHER")
    counts = latest.groupby(["round", "zone"]).size().unstack(fill_value=0)
    for zone in ("A", "B", "MID", "OTHER"):
        if zone not in counts:
            counts[zone] = 0
    counts = counts[["A", "B", "MID", "OTHER"]]

    def dominant(row: pd.Series) -> str:
        zones = row[["A", "B", "MID", "OTHER"]]
        maximum = int(zones.max())
        if maximum == 0:
            return "OTHER"
        leaders = zones.loc[zones == maximum].index.tolist()
        return leaders[0] if len(leaders) == 1 else "MIXED"

    counts["dominant_zone"] = counts.apply(dominant, axis=1)
    counts.insert(0, "seconds", float(sample_second))
    return counts.reset_index()


def shape_timeline(
    data: MatchData,
    team: str,
    side: str,
    sample_seconds: tuple[float, ...] = (20.0, 40.0, 60.0),
) -> pd.DataFrame:
    """Stack auditable round shapes at several elapsed-time checkpoints."""
    frames = [position_shapes(data, team, side, second) for second in sample_seconds]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(
            columns=["round", "seconds", "A", "B", "MID", "OTHER", "dominant_zone"]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["round", "seconds"])


def round_routes(
    data: MatchData,
    team: str,
    side: str,
    sample_seconds: tuple[float, ...] = (20.0, 40.0, 60.0),
) -> pd.DataFrame:
    """Return one auditable row per side-round and checkpoint.

    Missing checkpoints are kept explicitly.  They mean the round had already
    ended, not that the last known shape should be carried forward.
    """
    round_numbers = rounds_for_side(data, team, side)
    columns = [
        "round", "seconds", "A", "B", "MID", "OTHER", "dominant_zone",
        "available", "won_round", "complete_route", "sequence",
    ]
    if not round_numbers:
        return pd.DataFrame(columns=columns)

    checkpoints = tuple(float(second) for second in sample_seconds)
    grid = pd.MultiIndex.from_product(
        [round_numbers, checkpoints], names=["round", "seconds"]
    ).to_frame(index=False)
    timeline = shape_timeline(data, team, side, checkpoints)
    routes = grid.merge(
        timeline,
        on=["round", "seconds"],
        how="left",
        validate="one_to_one",
    )
    for zone in ("A", "B", "MID", "OTHER"):
        routes[zone] = routes[zone].fillna(0).astype(int)
    routes["available"] = routes["dominant_zone"].notna()

    winner_lookup = data.rounds.set_index("round")["winner"]
    routes["won_round"] = routes["round"].map(winner_lookup).eq(team)
    coverage = routes.groupby("round")["available"].transform("sum")
    routes["complete_route"] = coverage.eq(len(checkpoints))

    complete = routes.loc[routes["complete_route"]].pivot(
        index="round", columns="seconds", values="dominant_zone"
    )
    sequence_lookup: dict[int, str] = {}
    if not complete.empty and set(checkpoints).issubset(complete.columns):
        sequence_lookup = (
            complete[list(checkpoints)]
            .astype(str)
            .agg("→".join, axis=1)
            .to_dict()
        )
    routes["sequence"] = routes["round"].map(sequence_lookup)
    return routes[columns].sort_values(["round", "seconds"]).reset_index(drop=True)


def shape_transitions(
    data: MatchData,
    team: str,
    side: str,
    sample_seconds: tuple[float, ...] = (20.0, 40.0, 60.0),
) -> pd.DataFrame:
    """Count complete, same-round dominant-zone sequences across checkpoints."""
    timeline = shape_timeline(data, team, side, sample_seconds)
    if timeline.empty:
        return pd.DataFrame(columns=["sequence", "rounds", "count", "share"])
    pivot = timeline.pivot(index="round", columns="seconds", values="dominant_zone")
    required = [float(second) for second in sample_seconds]
    if not set(required).issubset(pivot.columns):
        return pd.DataFrame(columns=["sequence", "rounds", "count", "share"])
    complete = pivot.dropna(subset=required).copy()
    if complete.empty:
        return pd.DataFrame(columns=["sequence", "rounds", "count", "share"])
    complete["sequence"] = complete[required].astype(str).agg("→".join, axis=1)
    grouped = (
        complete.reset_index()
        .groupby("sequence", as_index=False)
        .agg(rounds=("round", lambda values: tuple(int(value) for value in values)), count=("round", "size"))
        .sort_values(["count", "sequence"], ascending=[False, True])
    )
    grouped["share"] = grouped["count"] / len(complete)
    return grouped.reset_index(drop=True)


def default_shape_summary(
    data: MatchData, team: str, sample_second: float = 20.0
) -> pd.DataFrame:
    """Compare the most frequent early-round team shape on T and CT sides."""
    records: list[dict[str, object]] = []
    for side in ("T", "CT"):
        shapes = position_shapes(data, team, side, sample_second)
        if shapes.empty:
            records.append(
                {
                    "side": side,
                    "seconds": float(sample_second),
                    "valid_rounds": 0,
                    "dominant_zone": "OTHER",
                    "rounds": tuple(),
                    "count": 0,
                    "share": 0.0,
                }
            )
            continue
        counts = shapes["dominant_zone"].value_counts()
        zone = str(counts.index[0])
        matching = shapes.loc[shapes["dominant_zone"] == zone, "round"].astype(int)
        records.append(
            {
                "side": side,
                "seconds": float(sample_second),
                "valid_rounds": len(shapes),
                "dominant_zone": zone,
                "rounds": tuple(matching.tolist()),
                "count": len(matching),
                "share": len(matching) / len(shapes),
            }
        )
    return pd.DataFrame.from_records(records)


def default_formation_summary(
    data: MatchData, team: str, sample_second: float = 20.0
) -> pd.DataFrame:
    """Summarize exact A/B/MID/home player-count formations for both sides."""
    records: list[dict[str, object]] = []
    for side in ("T", "CT"):
        shapes = position_shapes(data, team, side, sample_second)
        if shapes.empty:
            records.append(
                {
                    "side": side,
                    "seconds": float(sample_second),
                    "valid_rounds": 0,
                    "formation": None,
                    "rounds": tuple(),
                    "count": 0,
                    "share": 0.0,
                    "is_repeated": False,
                }
            )
            continue

        shapes = shapes.copy()
        home_label = "匪家" if side == "T" else "警家"
        shapes["formation"] = shapes.apply(
            lambda row: (
                f"A{int(row['A'])}·B{int(row['B'])}·中{int(row['MID'])}"
                f"·{home_label}{int(row['OTHER'])}"
            ),
            axis=1,
        )
        grouped = (
            shapes.groupby("formation", as_index=False)
            .agg(
                rounds=("round", lambda values: tuple(int(value) for value in values)),
                count=("round", "size"),
            )
            .sort_values(["count", "formation"], ascending=[False, True])
        )
        top = grouped.iloc[0]
        count = int(top["count"])
        records.append(
            {
                "side": side,
                "seconds": float(sample_second),
                "valid_rounds": len(shapes),
                "formation": str(top["formation"]),
                "rounds": tuple(top["rounds"]),
                "count": count,
                "share": count / len(shapes),
                "is_repeated": count >= 2,
            }
        )
    return pd.DataFrame.from_records(records)


def t_entry_results(data: MatchData, team: str) -> pd.DataFrame:
    """Return only the round result after a T-side opening kill.

    It deliberately does not attach later positions, plant sites or movement to
    the entry.  Those are joint outcomes of both teams' mid-round decisions.
    """
    t_rounds = set(rounds_for_side(data, team, "T"))
    firsts = data.kills.loc[
        data.kills["is_first_kill"] & data.kills["round"].isin(t_rounds)
    ].sort_values("round")
    round_lookup = data.rounds.set_index("round")
    records: list[dict[str, object]] = []
    for first in firsts.itertuples():
        round_num = int(first.round)
        earned = first.attacker_team == team
        round_row = round_lookup.loc[round_num]
        records.append({
            "round": round_num,
            "first_kill_seconds": float(first.seconds),
            "first_kill_team": str(first.attacker_team),
            "earned_entry": bool(earned),
            "won_round": round_row["winner"] == team,
        })
    return pd.DataFrame.from_records(records)


def opening_contact_evidence(data: MatchData, team: str, side: str) -> pd.DataFrame:
    """Return one auditable row for each side-round's first kill.

    This is deliberately an event index, not a tactic classifier.  The two
    nearest player samples are used only to attach a replay-friendly area
    label to the kill; no claim is made about why either team was there.
    """
    columns = [
        "round", "seconds", "killer", "victim", "killer_team", "killer_area",
        "victim_area", "first_kill_for", "winner", "won_round",
        "team_alive_after_5s", "team_zone_after_5s",
        "opponent_alive_after_5s", "opponent_zone_after_5s",
    ]
    round_numbers = set(rounds_for_side(data, team, side))
    if not round_numbers or data.kills.empty:
        return pd.DataFrame(columns=columns)

    firsts = data.kills.loc[
        data.kills["is_first_kill"] & data.kills["round"].isin(round_numbers)
    ].sort_values(["round", "seconds"])
    if firsts.empty:
        return pd.DataFrame(columns=columns)

    winner_lookup = data.rounds.set_index("round")["winner"]
    opponent = data.team_b if team == data.team_a else data.team_a

    def area_at(round_num: int, player: str, seconds: float) -> str:
        rows = data.positions.loc[
            (data.positions["round"] == round_num)
            & (data.positions["player"] == player)
        ]
        if rows.empty:
            return ""
        nearest = rows.assign(distance=(rows["seconds"] - seconds).abs())
        nearest = nearest.loc[nearest["distance"].idxmin()]
        if float(nearest["distance"]) > 0.75:
            return ""
        return str(nearest.get("area", "") or "")

    def state_at(round_num: int, team_name: str, seconds: float) -> tuple[int | None, str | None]:
        rows = data.positions.loc[
            (data.positions["round"] == round_num)
            & (data.positions["team"] == team_name)
            & (data.positions["seconds"] <= seconds)
        ]
        if rows.empty:
            return None, None
        if float(rows["seconds"].max()) < seconds - 0.75:
            return None, None
        latest = rows.loc[rows.groupby("player")["seconds"].idxmax()].copy()
        if "health" in latest:
            latest = latest.loc[latest["health"] > 0]
        if latest.empty:
            return 0, None
        zones = latest["area"].map(AREA_GROUP).fillna("OTHER")
        counts = zones.value_counts()
        top = counts[counts == counts.iloc[0]].index.tolist()
        return int(len(latest)), (str(top[0]) if len(top) == 1 else "MIXED")

    records: list[dict[str, object]] = []
    for first in firsts.itertuples():
        round_num = int(first.round)
        seconds = float(first.seconds)
        killer_team = str(first.attacker_team)
        winner = str(winner_lookup.get(round_num, ""))
        team_alive, team_zone = state_at(round_num, team, seconds + 5.0)
        opponent_alive, opponent_zone = state_at(round_num, opponent, seconds + 5.0)
        records.append(
            {
                "round": round_num,
                "seconds": seconds,
                "killer": str(first.attacker),
                "victim": str(first.victim),
                "killer_team": killer_team,
                "killer_area": area_at(round_num, str(first.attacker), seconds),
                "victim_area": area_at(round_num, str(first.victim), seconds),
                "first_kill_for": "本队" if killer_team == team else "对手",
                "winner": winner,
                "won_round": winner == team,
                "team_alive_after_5s": team_alive,
                "team_zone_after_5s": team_zone,
                "opponent_alive_after_5s": opponent_alive,
                "opponent_zone_after_5s": opponent_zone,
            }
        )
    return pd.DataFrame.from_records(records, columns=columns)


def build_tactical_findings(data: MatchData, team: str) -> list[TacticalFinding]:
    """Return only single-match facts that do not infer tactical intent.

    Plant sites, positions after a kill and late-round movement are joint
    outcomes of both teams' decisions.  They are intentionally left in the
    replay UI rather than promoted into an automatic team "finding" here.
    """
    findings: list[TacticalFinding] = []
    entry_results = t_entry_results(data, team)
    earned = entry_results.loc[entry_results["earned_entry"]] if not entry_results.empty else entry_results
    if not earned.empty:
        wins = int(earned["won_round"].sum())
        findings.append(TacticalFinding(
            kind="entry_conversion",
            title="T 方先拿首杀后的回合结果",
            summary=(
                f"{team} 本场 T 方拿到 {len(earned)} 次首杀，随后赢下 {wins} 回合，"
                f"条件转化率为 {wins / len(earned):.0%}。"
                "这是本场结果统计，不解释首杀后的战术选择。"
            ),
            sample_size=len(earned),
            evidence=tuple(
                TacticalEvidence(int(row.round), float(row.first_kill_seconds), "本队取得首杀")
                for row in earned.itertuples()
            ),
        ))
    return findings
