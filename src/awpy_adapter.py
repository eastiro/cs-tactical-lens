"""Awpy -> stable tables, with a persisted schema audit for every real demo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schema import MatchData, validate_match

# Awpy 2.x reports 128 for this SourceTV file, but its game-state tick counter
# advances at 64 ticks per real second. Player kinematics (roughly 220-250 u/s)
# and smoke lifetime both independently confirm the 64 Hz gameplay timebase.
TICKRATE = 64

UTILITY_PROJECTILES = {
    "CSmokeGrenadeProjectile": "smoke",
    "CFlashbangProjectile": "flash",
    "CHEGrenadeProjectile": "he",
    "CMolotovProjectile": "molotov",
    "CDecoyProjectile": "decoy",
}

ECONOMY_PLAYER_PROPS = [
    "inventory",
    "current_equip_value",
    "armor_value",
    "has_defuser",
    "has_helmet",
    # demoparser2 exposes money services through their full netprop names.
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount",
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount",
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound",
]

MONEY_COLUMNS = {
    "cash_after_buy": "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount",
    "start_cash": "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount",
    "cash_spent": "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound",
}


def _frame(value: Any) -> pd.DataFrame:
    """Accept Awpy Polars frames as well as DataFrames supplied by regression tests."""
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return value.to_pandas()


def _required(frame: pd.DataFrame, label: str, columns: set[str]) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"Awpy 的 {label} 缺少必要字段：{', '.join(sorted(missing))}")


def _column(frame: pd.DataFrame, candidates: list[str], label: str) -> str:
    found = next((name for name in candidates if name in frame.columns), None)
    if found is None:
        raise ValueError(f"Awpy 的 {label} 缺少可用字段（尝试过：{', '.join(candidates)}）")
    return found


def _team_by_round_and_side(ticks: pd.DataFrame) -> dict[tuple[int, str], str]:
    rows = ticks.dropna(subset=["team", "side"])
    grouped = rows.groupby(["round", "side"])["team"].agg(lambda values: values.mode().iat[0])
    return {(int(round_num), str(side).lower()): str(team) for (round_num, side), team in grouped.items()}


def _normalise_rounds(raw: pd.DataFrame, teams: dict[tuple[int, str], str]) -> tuple[pd.DataFrame, str, str]:
    _required(raw, "rounds", {"round_num", "freeze_end", "end", "winner", "reason"})
    rounds = raw.copy().sort_values("round_num")
    rounds["round"] = rounds["round_num"].astype(int)
    rounds["winning_side"] = rounds["winner"].astype(str).str.lower().replace({"terrorist": "t", "counter-terrorist": "ct"})
    rounds["winner"] = [teams.get((round_num, side), f"{side.upper()} side") for round_num, side in zip(rounds["round"], rounds["winning_side"], strict=True)]
    unique_teams = list(dict.fromkeys(team for team in teams.values() if not team.endswith(" side")))
    team_a, team_b = (unique_teams + ["Team A", "Team B"])[:2]
    rounds["team_a_score"] = (rounds["winner"] == team_a).cumsum()
    rounds["team_b_score"] = (rounds["winner"] == team_b).cumsum()
    plant_tick = pd.to_numeric(rounds.get("bomb_plant", pd.Series(pd.NA, index=rounds.index)), errors="coerce")
    rounds["bomb_plant_seconds"] = (plant_tick - rounds["freeze_end"]) / TICKRATE
    rounds["bomb_site"] = (
        rounds.get("bomb_site", pd.Series("not_planted", index=rounds.index))
        .astype(str)
        .str.lower()
        .map({"bombsite_a": "A", "bombsite_b": "B"})
    )
    return rounds[[
        "round", "winner", "winning_side", "team_a_score", "team_b_score", "reason",
        "freeze_end", "end", "bomb_plant_seconds", "bomb_site",
    ]], team_a, team_b


def _normalise_ticks(raw: pd.DataFrame, raw_rounds: pd.DataFrame) -> pd.DataFrame:
    _required(raw, "ticks", {"round_num", "tick", "name", "side", "X", "Y", "place"})
    ticks = raw.copy()
    team_column = _column(ticks, ["team_clan_name", "team"], "ticks 的战队名称")
    freeze = raw_rounds[["round_num", "freeze_end"]]
    ticks = ticks.merge(freeze, on="round_num", how="left", validate="many_to_one")
    ticks["seconds"] = ((ticks["tick"] - ticks["freeze_end"]) / TICKRATE).clip(lower=0)
    ticks["team"] = ticks[team_column].astype(str).str.strip()
    ticks["side"] = ticks["side"].astype(str).str.upper()
    ticks = ticks.loc[ticks["team"].notna() & ticks["team"].ne("") & ticks["team"].ne("nan")]
    ticks = ticks.rename(columns={"round_num": "round", "name": "player", "X": "x", "Y": "y", "place": "area"})
    if "health" not in ticks:
        ticks["health"] = 100
    return ticks[["round", "player", "team", "side", "seconds", "x", "y", "area", "health", "tick"]]


def _normalise_economy_snapshots(raw: pd.DataFrame, raw_rounds: pd.DataFrame) -> pd.DataFrame:
    """Persist one auditable freeze-end equipment/money row per player.

    A parser or fixture that does not expose the optional economy props returns
    an empty frame, keeping older bundles and tests fully backward compatible.
    """
    required = {"round_num", "tick", "name"}
    if raw.empty or not required.issubset(raw.columns):
        return pd.DataFrame()
    available = {"inventory", "current_equip_value", "armor", "has_defuser", "has_helmet"}
    available.update(name for name in MONEY_COLUMNS.values() if name in raw.columns)
    if not (available & set(raw.columns)):
        return pd.DataFrame()
    snapshots = raw.copy()
    freeze = raw_rounds[["round_num", "freeze_end"]].copy()
    snapshots = snapshots.merge(freeze, on="round_num", how="left", validate="many_to_one")
    snapshots = snapshots.loc[snapshots["tick"] >= snapshots["freeze_end"]].sort_values(
        ["round_num", "name", "tick"]
    )
    snapshots = snapshots.drop_duplicates(["round_num", "name"], keep="first")
    if snapshots.empty:
        return pd.DataFrame()
    result = pd.DataFrame({
        "round": snapshots["round_num"].astype(int),
        "tick": snapshots["tick"].astype(int),
        "player": snapshots["name"].astype(str),
        "team": snapshots.get("team_clan_name", pd.Series("", index=snapshots.index)).astype(str),
        "side": snapshots.get("side", pd.Series("", index=snapshots.index)).astype(str).str.upper(),
        "seconds": (snapshots["tick"] - snapshots["freeze_end"]) / TICKRATE,
        "inventory": snapshots.get("inventory", pd.Series("[]", index=snapshots.index)).map(_serialise_inventory),
        "current_equip_value": pd.to_numeric(
            snapshots.get("current_equip_value", pd.Series(pd.NA, index=snapshots.index)), errors="coerce"
        ),
        "armor": pd.to_numeric(snapshots.get("armor", pd.Series(pd.NA, index=snapshots.index)), errors="coerce"),
        "has_helmet": snapshots.get("has_helmet", pd.Series(False, index=snapshots.index)).fillna(False).astype(bool),
        "has_defuser": snapshots.get("has_defuser", pd.Series(False, index=snapshots.index)).fillna(False).astype(bool),
    })
    for target, source in MONEY_COLUMNS.items():
        result[target] = pd.to_numeric(
            snapshots.get(source, pd.Series(pd.NA, index=snapshots.index)), errors="coerce"
        )
    return result.reset_index(drop=True)


def _serialise_inventory(value: Any) -> str:
    """Canonicalise Awpy inventory values for stable comparison and CSV output."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False)
    return "[]"


def _normalise_loadout_events(raw: pd.DataFrame, raw_rounds: pd.DataFrame) -> pd.DataFrame:
    """Compress post-freeze inventory state into a player-visible event stream.

    Raw tick tables are intentionally not persisted: a single demo contains
    millions of rows.  The replay needs only the first state after freeze end
    plus later ticks where a viewer-visible piece of equipment actually
    changes.  Equipment value and account are carried on those retained rows
    as context, but they deliberately do not trigger their own event: money
    changes alone would make the replay sidebar refresh without any visible
    loadout change.
    """
    required = {"round_num", "tick", "name"}
    if raw.empty or not required.issubset(raw.columns) or "inventory" not in raw.columns:
        return pd.DataFrame()
    boundaries = raw_rounds[["round_num", "freeze_end", "end"]].copy()
    events = raw.merge(boundaries, on="round_num", how="left", validate="many_to_one")
    events = events.loc[
        events["tick"].ge(events["freeze_end"])
        & events["tick"].le(events["end"])
    ].copy()
    # Demo frames occasionally contain a spectator or residual player record
    # without a team assignment. It cannot belong to either five-player HUD,
    # so keeping it would create a bogus eleventh player in the replay panel.
    if "team_clan_name" in events.columns:
        team_names = events["team_clan_name"].fillna("").astype(str).str.strip()
        events = events.loc[team_names.ne("")].copy()
    if events.empty:
        return pd.DataFrame()
    events = events.sort_values(["round_num", "name", "tick"])
    events["inventory"] = events["inventory"].map(_serialise_inventory)
    events["current_equip_value"] = pd.to_numeric(
        events.get("current_equip_value", pd.Series(pd.NA, index=events.index)), errors="coerce"
    )
    events["armor"] = pd.to_numeric(
        events.get("armor", events.get("armor_value", pd.Series(pd.NA, index=events.index))), errors="coerce"
    )
    events["has_helmet"] = events.get("has_helmet", pd.Series(False, index=events.index)).fillna(False).astype(bool)
    events["has_defuser"] = events.get("has_defuser", pd.Series(False, index=events.index)).fillna(False).astype(bool)
    events["account"] = pd.to_numeric(
        events.get(MONEY_COLUMNS["cash_after_buy"], pd.Series(pd.NA, index=events.index)), errors="coerce"
    )
    signature_columns = ["inventory", "armor", "has_helmet", "has_defuser"]
    # CSV-safe state signature: the first row for each player is always kept,
    # then only observably changed loadouts survive.
    events["_state"] = events[signature_columns].astype(str).agg("\x1f".join, axis=1)
    events = events.loc[
        events["_state"].ne(events.groupby(["round_num", "name"])["_state"].shift())
    ].copy()
    result = pd.DataFrame({
        "round": events["round_num"].astype(int),
        "tick": events["tick"].astype(int),
        "seconds": (events["tick"] - events["freeze_end"]) / TICKRATE,
        "player": events["name"].astype(str),
        "team": events.get("team_clan_name", pd.Series("", index=events.index)).astype(str),
        "side": events.get("side", pd.Series("", index=events.index)).astype(str).str.upper(),
        "inventory": events["inventory"],
        "current_equip_value": events["current_equip_value"],
        "armor": events["armor"],
        "has_helmet": events["has_helmet"],
        "has_defuser": events["has_defuser"],
        "account": events["account"],
    })
    return result.reset_index(drop=True)


def _normalise_kills(raw: pd.DataFrame, raw_rounds: pd.DataFrame, teams: dict[tuple[int, str], str]) -> pd.DataFrame:
    _required(raw, "kills", {"round_num", "tick", "attacker_name", "victim_name", "attacker_side", "attacker_X", "attacker_Y"})
    freeze_lookup = raw_rounds.set_index("round_num")["freeze_end"]
    kills = raw.copy().sort_values(["round_num", "tick"])
    kills["round"] = kills["round_num"].astype(int)
    attacker_side_key = kills["attacker_side"].astype(str).str.lower()
    kills["attacker_team"] = [teams.get((round_num, side), f"{side.upper()} side") for round_num, side in zip(kills["round"], attacker_side_key, strict=True)]
    kills["attacker_side"] = attacker_side_key.str.upper()
    kills["seconds"] = [(tick - freeze_lookup.loc[round_num]) / TICKRATE for tick, round_num in zip(kills["tick"], kills["round_num"], strict=True)]
    kills["is_first_kill"] = ~kills.duplicated("round_num")
    victim_side = kills.get("victim_side", pd.Series("", index=kills.index)).astype(str).str.lower()
    kills["victim_team"] = [teams.get((round_num, side), f"{side.upper()} side") for round_num, side in zip(kills["round"], victim_side, strict=True)]
    kills["weapon"] = kills.get("weapon", pd.Series("unknown", index=kills.index)).fillna("unknown")
    kills["victim_x"] = kills.get("victim_X", kills["attacker_X"])
    kills["victim_y"] = kills.get("victim_Y", kills["attacker_Y"])
    kills["assister"] = kills.get("assister_name", pd.Series("", index=kills.index)).fillna("").astype(str)
    kills["assisted_flash"] = kills.get("assistedflash", pd.Series(False, index=kills.index)).fillna(False).astype(bool)
    return kills.rename(columns={"attacker_name": "attacker", "victim_name": "victim", "attacker_X": "x", "attacker_Y": "y"})[
        ["round", "tick", "attacker", "victim", "attacker_team", "victim_team", "attacker_side", "assister", "assisted_flash", "x", "y", "victim_x", "victim_y", "weapon", "seconds", "is_first_kill"]
    ]


def _normalise_damages(
    raw: pd.DataFrame, raw_rounds: pd.DataFrame, teams: dict[tuple[int, str], str]
) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    _required(
        raw,
        "damages",
        {"round_num", "tick", "attacker_name", "victim_name", "attacker_side", "victim_side", "weapon"},
    )
    freeze_lookup = raw_rounds.set_index("round_num")["freeze_end"]
    damages = raw.copy().sort_values(["round_num", "tick"])
    damages["round"] = damages["round_num"].astype(int)
    attacker_side = damages["attacker_side"].astype(str).str.lower()
    victim_side = damages["victim_side"].astype(str).str.lower()
    damages["attacker_team"] = [
        teams.get((round_num, side), f"{side.upper()} side")
        for round_num, side in zip(damages["round"], attacker_side, strict=True)
    ]
    damages["victim_team"] = [
        teams.get((round_num, side), f"{side.upper()} side")
        for round_num, side in zip(damages["round"], victim_side, strict=True)
    ]
    damages["attacker_side"] = attacker_side.str.upper()
    damages["victim_side"] = victim_side.str.upper()
    damages["seconds"] = [
        (tick - freeze_lookup.loc[round_num]) / TICKRATE
        for tick, round_num in zip(damages["tick"], damages["round_num"], strict=True)
    ]
    damages["damage_health"] = pd.to_numeric(
        damages.get("dmg_health_real", damages.get("dmg_health", 0)), errors="coerce"
    ).fillna(0)
    damages["damage_armor"] = pd.to_numeric(damages.get("dmg_armor", 0), errors="coerce").fillna(0)
    damages["x"] = pd.to_numeric(damages.get("victim_X"), errors="coerce")
    damages["y"] = pd.to_numeric(damages.get("victim_Y"), errors="coerce")
    return damages.rename(columns={"attacker_name": "attacker", "victim_name": "victim"})[
        [
            "round", "tick", "seconds", "attacker", "victim", "attacker_team", "victim_team",
            "attacker_side", "victim_side", "weapon", "damage_health", "damage_armor", "x", "y",
        ]
    ]


def _normalise_bomb_events(
    raw: pd.DataFrame,
    raw_rounds: pd.DataFrame,
    positions: pd.DataFrame,
    teams: dict[tuple[int, str], str],
) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    _required(raw, "bomb_events", {"round_num", "tick", "event"})
    freeze_lookup = raw_rounds.set_index("round_num")["freeze_end"]
    events = raw.copy().sort_values(["round_num", "tick"])
    events["round"] = events["round_num"].astype(int)
    events["seconds"] = [
        (tick - freeze_lookup.loc[round_num]) / TICKRATE
        for tick, round_num in zip(events["tick"], events["round_num"], strict=True)
    ]
    events["player"] = events.get("name", pd.Series("", index=events.index)).fillna("").astype(str)
    player_teams = (
        positions.groupby(["round", "player"])["team"].agg(lambda values: values.mode().iat[0]).to_dict()
    )
    inferred_teams = []
    for row in events.itertuples():
        team = player_teams.get((int(row.round), str(row.player)))
        if not team and str(row.event) in {"plant", "detonate"}:
            team = teams.get((int(row.round), "t"))
        elif not team and str(row.event) == "defuse":
            team = teams.get((int(row.round), "ct"))
        inferred_teams.append(team or "")
    events["team"] = inferred_teams
    events["bombsite"] = (
        events.get("bombsite", pd.Series("", index=events.index))
        .astype(str)
        .str.lower()
        .map({"bombsite_a": "A", "bombsite_b": "B", "a": "A", "b": "B"})
    )
    events["x"] = pd.to_numeric(events.get("X"), errors="coerce")
    events["y"] = pd.to_numeric(events.get("Y"), errors="coerce")
    return events[["round", "tick", "seconds", "event", "player", "team", "bombsite", "x", "y"]]


def _normalise_grenades(
    raw: pd.DataFrame,
    raw_rounds: pd.DataFrame,
    positions: pd.DataFrame,
    effects: pd.DataFrame | None = None,
) -> pd.DataFrame:
    _required(raw, "grenades", {"round_num", "entity_id", "thrower", "grenade_type", "tick", "X", "Y"})
    freeze_lookup = raw_rounds.set_index("round_num")["freeze_end"]
    trajectories = raw.loc[raw["grenade_type"].isin(UTILITY_PROJECTILES)].dropna(subset=["X", "Y"]).copy()
    trajectories["seconds"] = [
        (tick - freeze_lookup.loc[round_num]) / TICKRATE
        for tick, round_num in zip(trajectories["tick"], trajectories["round_num"], strict=True)
    ]
    trajectory_keys = ["round_num", "entity_id", "grenade_type", "thrower"]
    trajectories = trajectories.loc[trajectories["seconds"] >= 0].sort_values(trajectory_keys + ["tick"])
    if trajectories.empty:
        return pd.DataFrame(columns=[
            "round", "thrower", "team", "grenade_type", "seconds", "land_seconds",
            "effect_end_seconds", "x", "y", "throw_x", "throw_y", "trajectory",
        ])
    # CS2 may reuse an entity id later in the same round. A gap starts a new projectile;
    # without this split, two separate grenades become one impossible 40-second flight.
    trajectory_groups = trajectories.groupby(trajectory_keys, sort=False)
    group_ids = trajectory_groups.ngroup()
    tick_gap = trajectory_groups["tick"].diff()
    coordinate_jump = (
        trajectory_groups["X"].diff().pow(2) + trajectory_groups["Y"].diff().pow(2)
    ).pow(0.5)
    starts_new_projectile = tick_gap.isna() | tick_gap.gt(TICKRATE * 8) | coordinate_jump.gt(128)
    trajectories["trajectory_segment"] = starts_new_projectile.groupby(group_ids).cumsum()
    keys = trajectory_keys + ["trajectory_segment"]
    earliest = trajectories.groupby(keys, as_index=False).first()
    movement = (
        trajectories.groupby(keys, sort=False)["X"].diff().pow(2)
        + trajectories.groupby(keys, sort=False)["Y"].diff().pow(2)
    ).pow(0.5)
    moving_trajectories = trajectories.loc[movement.gt(0.05)]
    latest = moving_trajectories.groupby(keys, as_index=False).last()[keys + ["tick", "X", "Y"]].rename(
        columns={"tick": "land_tick", "X": "land_x", "Y": "land_y"}
    )
    earliest = earliest.merge(latest, on=keys, how="left", validate="one_to_one")
    earliest["effect_end_tick"] = pd.NA
    if effects is not None and not effects.empty:
        used_effects: set[int] = set()
        for index, grenade in earliest.iterrows():
            effect_type = UTILITY_PROJECTILES.get(str(grenade["grenade_type"]))
            if effect_type not in {"smoke", "molotov"}:
                continue
            candidates = effects.loc[
                (effects["_effect_type"] == effect_type)
                & (effects["round_num"] == grenade["round_num"])
                & effects["start_tick"].between(grenade["tick"], grenade["tick"] + TICKRATE * 8)
            ].copy()
            if "thrower_name" in candidates and candidates["thrower_name"].eq(grenade["thrower"]).any():
                candidates = candidates.loc[candidates["thrower_name"] == grenade["thrower"]]
            candidates = candidates.loc[~candidates.index.isin(used_effects)]
            if candidates.empty:
                continue
            # Some official demos omit a projectile landing coordinate/tick.
            # The throw is still a valid utility event; fall back to its
            # creation tick for optional smoke/molotov effect matching instead
            # of turning an all-NaN distance column into a parser failure.
            anchor_tick = grenade["land_tick"] if pd.notna(grenade["land_tick"]) else grenade["tick"]
            candidates["_distance"] = (candidates["start_tick"] - anchor_tick).abs()
            candidates.loc[candidates["entity_id"] == grenade["entity_id"], "_distance"] -= TICKRATE
            candidates = candidates.loc[candidates["_distance"].notna()]
            if candidates.empty:
                continue
            chosen_index = candidates["_distance"].idxmin()
            chosen = candidates.loc[chosen_index]
            used_effects.add(chosen_index)
            earliest.at[index, "land_tick"] = chosen["start_tick"]
            earliest.at[index, "effect_end_tick"] = chosen["end_tick"]
            if "X" in chosen and pd.notna(chosen["X"]):
                earliest.at[index, "land_x"] = chosen["X"]
                earliest.at[index, "land_y"] = chosen["Y"]
    earliest["land_seconds"] = [
        (tick - freeze_lookup.loc[round_num]) / TICKRATE
        for tick, round_num in zip(earliest["land_tick"], earliest["round_num"], strict=True)
    ]
    flight_caps = {
        "CSmokeGrenadeProjectile": 4.0,
        "CFlashbangProjectile": 2.5,
        "CHEGrenadeProjectile": 2.5,
        "CMolotovProjectile": 2.5,
        "CDecoyProjectile": 4.0,
    }
    maximum_land = earliest["seconds"] + earliest["grenade_type"].map(flight_caps).fillna(4.0)
    earliest["land_seconds"] = earliest[["land_seconds"]].join(maximum_land.rename("maximum_land")).min(axis=1)
    earliest["land_tick"] = [
        freeze_lookup.loc[round_num] + seconds * TICKRATE
        for round_num, seconds in zip(earliest["round_num"], earliest["land_seconds"], strict=True)
    ]
    earliest["effect_end_seconds"] = [
        pd.NA if pd.isna(tick) else (tick - freeze_lookup.loc[round_num]) / TICKRATE
        for tick, round_num in zip(earliest["effect_end_tick"], earliest["round_num"], strict=True)
    ]
    cutoff_lookup = {
        tuple(values[:-1]): float(values[-1])
        for values in earliest[keys + ["land_tick"]].itertuples(index=False, name=None)
    }
    trajectory_paths: dict[tuple[Any, ...], str] = {}
    for key, path_rows in trajectories.groupby(keys, sort=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        active = path_rows.loc[path_rows["tick"] <= cutoff_lookup[key_tuple]].copy()
        if active.empty:
            active = path_rows.iloc[[0]].copy()
        active["sample_bin"] = (active["seconds"] * 16).round().astype(int)
        active = active.drop_duplicates("sample_bin", keep="last")
        trajectory_paths[key_tuple] = json.dumps(
            [
                [round(float(row.seconds), 4), round(float(row.X), 3), round(float(row.Y), 3)]
                for row in active.itertuples()
            ],
            separators=(",", ":"),
        )
    earliest["trajectory"] = [
        trajectory_paths[tuple(values)]
        for values in earliest[keys].itertuples(index=False, name=None)
    ]
    teams = positions[["round", "player", "team"]].drop_duplicates(["round", "player"])
    earliest = earliest.merge(teams, left_on=["round_num", "thrower"], right_on=["round", "player"], how="left")
    earliest["team"] = earliest["team"].fillna("Unknown")
    earliest["grenade_type"] = earliest["grenade_type"].map(UTILITY_PROJECTILES)
    earliest = earliest.drop(columns=["round", "player"]).rename(
        columns={"round_num": "round", "X": "throw_x", "Y": "throw_y", "land_x": "x", "land_y": "y"}
    )
    return earliest[[
        "round", "thrower", "team", "grenade_type", "seconds", "land_seconds", "effect_end_seconds",
        "x", "y", "throw_x", "throw_y", "trajectory",
    ]]


def normalise_awpy_frames(frames: dict[str, Any], *, map_name: str = "Unknown map", match_name: str = "Imported CS2 demo") -> MatchData:
    """Make parser output analyzable and preserve its observed schema for auditability."""
    raw_rounds = _frame(frames["rounds"])
    raw_ticks = _frame(frames["ticks"])
    raw_kills = _frame(frames["kills"])
    raw_grenades = _frame(frames["grenades"])
    economy_snapshots = _normalise_economy_snapshots(raw_ticks, raw_rounds)
    loadout_events = _normalise_loadout_events(raw_ticks, raw_rounds)
    positions = _normalise_ticks(raw_ticks, raw_rounds)
    teams = _team_by_round_and_side(positions)
    rounds, team_a, team_b = _normalise_rounds(raw_rounds, teams)
    kills = _normalise_kills(raw_kills, raw_rounds, teams)
    effect_frames = []
    for name, effect_type in (("smokes", "smoke"), ("infernos", "molotov")):
        if name in frames:
            effect = _frame(frames[name])
            if not effect.empty:
                _required(effect, name, {"round_num", "entity_id", "start_tick", "end_tick"})
                effect["_effect_type"] = effect_type
                effect_frames.append(effect)
    effects = pd.concat(effect_frames, ignore_index=True) if effect_frames else None
    grenades = _normalise_grenades(raw_grenades, raw_rounds, positions, effects)
    damages = _normalise_damages(_frame(frames["damages"]), raw_rounds, teams) if "damages" in frames else pd.DataFrame()
    bomb_events = (
        _normalise_bomb_events(_frame(frames["bomb_events"]), raw_rounds, positions, teams)
        if "bomb_events" in frames
        else pd.DataFrame()
    )
    if team_a.endswith(" side") or team_b.endswith(" side"):
        raise ValueError("demo 未给出两支队伍的稳定名称，已拒绝生成可能误导的对局结论。")
    data = MatchData(
        match_name, map_name, team_a, team_b, "demo", rounds, kills, positions, grenades,
        metadata={"parser": "awpy", "tickrate": TICKRATE, "observed_columns": {name: list(_frame(frame).columns) for name, frame in frames.items()}},
        damages=damages,
        bomb_events=bomb_events,
        economy_snapshots=economy_snapshots,
        loadout_events=loadout_events,
    )
    validate_match(data)
    return data


def write_normalized_bundle(data: MatchData, output_dir: str | Path) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("rounds", "kills", "positions", "grenades"):
        getattr(data, name).to_csv(output / f"{name}.csv", index=False)
    for name in ("damages", "bomb_events", "economy_snapshots", "loadout_events"):
        frame = getattr(data, name)
        if not frame.empty:
            frame.to_csv(output / f"{name}.csv", index=False)
    (output / "metadata.json").write_text(json.dumps({"match_name": data.match_name, "map_name": data.map_name, "team_a": data.team_a, "team_b": data.team_b, **data.metadata}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _read_csv_or_gz(path: Path) -> pd.DataFrame:
    """Read a CSV file, falling back to ``.csv.gz`` if the plain file is absent."""
    if path.is_file():
        return pd.read_csv(path)
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.is_file():
        return pd.read_csv(gz_path)
    raise FileNotFoundError(f"找不到 {path} 或 {gz_path}")


def load_normalized_bundle(output_dir: str | Path) -> MatchData:
    """Reload an audited local bundle without parsing the demo again."""
    output = Path(output_dir)
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    damages_path = output / "damages.csv"
    bomb_events_path = output / "bomb_events.csv"
    economy_path = output / "economy_snapshots.csv"
    loadout_events_path = output / "loadout_events.csv"
    data = MatchData(
        metadata["match_name"], metadata["map_name"], metadata["team_a"], metadata["team_b"], "demo",
        _read_csv_or_gz(output / "rounds.csv"),
        _read_csv_or_gz(output / "kills.csv"),
        _read_csv_or_gz(output / "positions.csv"),
        _read_csv_or_gz(output / "grenades.csv"),
        metadata={key: value for key, value in metadata.items() if key not in {"match_name", "map_name", "team_a", "team_b"}},
        damages=pd.read_csv(damages_path) if damages_path.is_file() else pd.DataFrame(),
        bomb_events=pd.read_csv(bomb_events_path) if bomb_events_path.is_file() else pd.DataFrame(),
        economy_snapshots=pd.read_csv(economy_path) if economy_path.is_file() else pd.DataFrame(),
        loadout_events=pd.read_csv(loadout_events_path) if loadout_events_path.is_file() else pd.DataFrame(),
    )
    validate_match(data)
    return data


def load_awpy_demo(path: str | Path) -> MatchData:
    from awpy import Demo

    demo = Demo(Path(path))
    demo.parse(player_props=["team_clan_name", *ECONOMY_PLAYER_PROPS])
    header = getattr(demo, "header", {}) or {}
    map_name = header.get("map_name") or header.get("map") or Path(path).stem
    frames = {
        "rounds": demo.rounds,
        "kills": demo.kills,
        "ticks": demo.ticks,
        "grenades": demo.grenades,
        "smokes": demo.smokes,
        "infernos": demo.infernos,
        "damages": demo.damages,
        "bomb_events": demo.bomb,
    }
    return normalise_awpy_frames(frames, map_name=map_name, match_name=Path(path).stem)
