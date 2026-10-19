"""Evidence-backed single-round situation timeline.

The chart only visualises explicit demo events: deaths and bomb actions.  It is
not a win-probability model and intentionally makes no tactical judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import plotly.graph_objects as go

from .schema import MatchData

EventKind = Literal["kill", "plant", "defuse", "detonate"]

T_COLOR = "#F0AA3C"
CT_COLOR = "#4DA3FF"
SURFACE = "#0e131b"
BORDER = "#1c2330"
TEXT = "#e1e7ef"
MUTED = "#78869a"
DIM = "#4b5769"
GREEN = "#47C97E"
RED = "#FF5F65"


@dataclass(frozen=True)
class RoundTimelineEvent:
    seconds: float
    kind: EventKind
    actor: str = ""
    victim: str = ""
    weapon: str = ""
    actor_side: str = ""
    victim_side: str = ""
    site: str = ""


def _round_side_by_team(data: MatchData, round_num: int) -> dict[str, str]:
    positions = data.positions.loc[data.positions["round"] == round_num]
    mapping: dict[str, str] = {}
    for team, rows in positions.groupby("team"):
        sides = rows["side"].dropna().astype(str).str.upper()
        if not sides.empty:
            mapping[str(team)] = str(sides.mode().iat[0])
    return mapping


def build_round_timeline(data: MatchData, round_num: int) -> list[RoundTimelineEvent]:
    """Build a chronological, auditable event list for one round."""
    sides = _round_side_by_team(data, round_num)
    events: list[RoundTimelineEvent] = []

    kills = data.kills.loc[data.kills["round"] == round_num].sort_values("seconds")
    for kill in kills.itertuples():
        actor_team = str(getattr(kill, "attacker_team", ""))
        victim_team = str(getattr(kill, "victim_team", ""))
        actor_side = sides.get(actor_team, str(getattr(kill, "attacker_side", "")).upper())
        victim_side = sides.get(victim_team, "")
        if victim_side not in {"T", "CT"} and actor_side in {"T", "CT"} and actor_team != victim_team:
            victim_side = "CT" if actor_side == "T" else "T"
        events.append(
            RoundTimelineEvent(
                seconds=float(kill.seconds),
                kind="kill",
                actor=str(kill.attacker),
                victim=str(kill.victim),
                weapon=str(getattr(kill, "weapon", "")),
                actor_side=actor_side,
                victim_side=victim_side,
            )
        )

    if not data.bomb_events.empty:
        bomb_rows = data.bomb_events.loc[
            (data.bomb_events["round"] == round_num)
            & data.bomb_events["event"].isin(["plant", "defuse", "detonate"])
        ].sort_values("seconds")
        round_row = data.rounds.loc[data.rounds["round"] == round_num]
        fallback_site = ""
        if not round_row.empty and "bomb_site" in round_row:
            value = round_row.iloc[0]["bomb_site"]
            fallback_site = "" if pd.isna(value) else str(value).upper()
        for bomb in bomb_rows.itertuples():
            raw_site = getattr(bomb, "bombsite", "")
            site = fallback_site if pd.isna(raw_site) or str(raw_site) == "" else str(raw_site).upper()
            team = str(getattr(bomb, "team", ""))
            events.append(
                RoundTimelineEvent(
                    seconds=float(bomb.seconds),
                    kind=str(bomb.event),
                    actor=str(getattr(bomb, "player", "")),
                    actor_side=sides.get(team, ""),
                    site=site,
                )
            )

    order = {"kill": 0, "plant": 1, "defuse": 2, "detonate": 3}
    return sorted(events, key=lambda event: (event.seconds, order[event.kind]))


def survivor_curves(
    events: list[RoundTimelineEvent],
    *,
    end_second: float | None = None,
) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    """Return T/CT alive-count step curves, decrementing the victim's side."""
    t_alive = 5
    ct_alive = 5
    t_curve: list[tuple[float, int]] = [(0.0, t_alive)]
    ct_curve: list[tuple[float, int]] = [(0.0, ct_alive)]

    for event in sorted(events, key=lambda item: item.seconds):
        if event.kind == "kill":
            if event.victim_side == "T":
                t_alive = max(0, t_alive - 1)
            elif event.victim_side == "CT":
                ct_alive = max(0, ct_alive - 1)
        t_curve.append((float(event.seconds), t_alive))
        ct_curve.append((float(event.seconds), ct_alive))

    if end_second is not None:
        end = float(end_second)
        if end > t_curve[-1][0]:
            t_curve.append((end, t_alive))
            ct_curve.append((end, ct_alive))
    return t_curve, ct_curve


def _event_description(event: RoundTimelineEvent) -> str:
    if event.kind == "kill":
        weapon = f" · {event.weapon}" if event.weapon else ""
        return f"{event.actor} → {event.victim}{weapon}"
    if event.kind == "plant":
        site = f" · {event.site} 区" if event.site else ""
        return f"{event.actor} 下包{site}"
    if event.kind == "defuse":
        return f"{event.actor} 拆包成功"
    return "C4 爆炸"


def render_round_timeline(
    events: list[RoundTimelineEvent],
    *,
    end_second: float,
    selected_second: float | None = None,
    height: int = 270,
) -> go.Figure:
    """Render alive-count curves and clickable event points."""
    end = max(float(end_second), max((event.seconds for event in events), default=0.0), 10.0)
    t_curve, ct_curve = survivor_curves(events, end_second=end)
    fig = go.Figure()

    for name, curve, color in (("T 存活", t_curve, T_COLOR), ("CT 存活", ct_curve, CT_COLOR)):
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in curve],
                y=[point[1] for point in curve],
                mode="lines",
                name=name,
                line=dict(color=color, width=3, shape="hv"),
                hovertemplate=f"<b>{name}</b>：%{{y}} 人<br>%{{x:.2f}} 秒<extra></extra>",
            )
        )

    alive_t = 5
    alive_ct = 5
    kill_x: list[float] = []
    kill_y: list[float] = []
    kill_colors: list[str] = []
    kill_custom: list[list[object]] = []
    bomb_x: list[float] = []
    bomb_y: list[float] = []
    bomb_colors: list[str] = []
    bomb_symbols: list[str] = []
    bomb_custom: list[list[object]] = []

    for event in sorted(events, key=lambda item: item.seconds):
        if event.kind == "kill":
            if event.victim_side == "T":
                alive_t = max(0, alive_t - 1)
                marker_y = alive_t
            elif event.victim_side == "CT":
                alive_ct = max(0, alive_ct - 1)
                marker_y = alive_ct
            else:
                marker_y = max(alive_t, alive_ct)
            kill_x.append(event.seconds)
            kill_y.append(marker_y)
            kill_colors.append(T_COLOR if event.actor_side == "T" else CT_COLOR if event.actor_side == "CT" else RED)
            kill_custom.append([event.seconds, _event_description(event)])
        else:
            bomb_x.append(event.seconds)
            bomb_y.append(5.55)
            bomb_colors.append({"plant": T_COLOR, "defuse": GREEN, "detonate": RED}[event.kind])
            bomb_symbols.append({"plant": "star", "defuse": "cross", "detonate": "x"}[event.kind])
            bomb_custom.append([event.seconds, _event_description(event)])

    if kill_x:
        fig.add_trace(
            go.Scatter(
                x=kill_x,
                y=kill_y,
                mode="markers",
                name="击杀",
                marker=dict(size=12, color=kill_colors, symbol="diamond", line=dict(width=1, color="#080b0f")),
                customdata=kill_custom,
                hovertemplate="<b>击杀</b><br>%{customdata[1]}<br>%{x:.2f} 秒<extra></extra>",
            )
        )
    if bomb_x:
        fig.add_trace(
            go.Scatter(
                x=bomb_x,
                y=bomb_y,
                mode="markers",
                name="炸弹事件",
                marker=dict(size=15, color=bomb_colors, symbol=bomb_symbols, line=dict(width=1, color="#080b0f")),
                customdata=bomb_custom,
                hovertemplate="<b>炸弹事件</b><br>%{customdata[1]}<br>%{x:.2f} 秒<extra></extra>",
            )
        )

    if selected_second is not None and 0 <= selected_second <= end:
        fig.add_vline(
            x=float(selected_second),
            line=dict(color="#eef3f8", width=1.5, dash="dot"),
            opacity=0.55,
        )

    fig.update_layout(
        height=height,
        margin=dict(l=42, r=18, t=28, b=42),
        paper_bgcolor="#080b0f",
        plot_bgcolor=SURFACE,
        font=dict(family="Inter, sans-serif", size=12, color=TEXT),
        hovermode="closest",
        dragmode=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(color=MUTED, size=11)),
        xaxis=dict(
            title=dict(text="回合经过时间（秒）", font=dict(color=MUTED, size=11)),
            range=[0, end],
            tickfont=dict(color=DIM, size=10),
            gridcolor="#1a212c",
            zeroline=False,
            dtick=10,
        ),
        yaxis=dict(
            title=dict(text="存活人数", font=dict(color=MUTED, size=11)),
            range=[-0.25, 6.1],
            tickvals=[0, 1, 2, 3, 4, 5],
            tickfont=dict(color=DIM, size=10),
            gridcolor="#1a212c",
            zeroline=False,
        ),
    )
    return fig
