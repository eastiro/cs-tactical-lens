"""Stable tables accepted by the analysis layer."""

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

DataKind = Literal["synthetic", "demo"]


@dataclass(frozen=True)
class MatchData:
    match_name: str
    map_name: str
    team_a: str
    team_b: str
    source_kind: DataKind
    rounds: pd.DataFrame
    kills: pd.DataFrame
    positions: pd.DataFrame
    grenades: pd.DataFrame
    metadata: dict[str, object] = field(default_factory=dict)
    damages: pd.DataFrame = field(default_factory=pd.DataFrame)
    bomb_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Optional V3.1 freeze-end player snapshot. Older bundles legitimately do
    # not have it and remain valid with an empty frame.
    economy_snapshots: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Optional V3.2 event-compressed inventory timeline. Each player has a
    # freeze-end baseline plus only the later ticks where their visible loadout
    # actually changes; older bundles legitimately keep this empty.
    loadout_events: pd.DataFrame = field(default_factory=pd.DataFrame)


ROUND_COLUMNS = {"round", "winner", "winning_side", "team_a_score", "team_b_score"}
KILL_COLUMNS = {"round", "attacker", "victim", "attacker_team", "attacker_side", "x", "y", "seconds", "is_first_kill"}
POSITION_COLUMNS = {"round", "player", "team", "side", "seconds", "x", "y", "area"}
GRENADE_COLUMNS = {"round", "thrower", "team", "grenade_type", "seconds", "x", "y"}
DAMAGE_COLUMNS = {"round", "attacker", "victim", "attacker_team", "weapon", "damage_health", "seconds"}
BOMB_EVENT_COLUMNS = {"round", "event", "seconds"}
ECONOMY_COLUMNS = {
    "round", "tick", "player", "team", "side", "seconds", "inventory",
    "current_equip_value", "armor", "has_helmet", "has_defuser",
    "start_cash", "cash_after_buy", "cash_spent",
}
LOADOUT_EVENT_COLUMNS = {
    "round", "tick", "seconds", "player", "team", "side", "inventory",
    "current_equip_value", "armor", "has_helmet", "has_defuser", "account",
}


def validate_match(data: MatchData) -> None:
    for label, frame, required in (("rounds", data.rounds, ROUND_COLUMNS), ("kills", data.kills, KILL_COLUMNS), ("positions", data.positions, POSITION_COLUMNS), ("grenades", data.grenades, GRENADE_COLUMNS)):
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{label} 缺少字段：{', '.join(sorted(missing))}")
    for label, frame, required in (
        ("damages", data.damages, DAMAGE_COLUMNS),
        ("bomb_events", data.bomb_events, BOMB_EVENT_COLUMNS),
        ("economy_snapshots", data.economy_snapshots, ECONOMY_COLUMNS),
        ("loadout_events", data.loadout_events, LOADOUT_EVENT_COLUMNS),
    ):
        if frame.empty:
            continue
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{label} 缺少字段：{', '.join(sorted(missing))}")
