"""Auditable playback states derived from compressed loadout events.

This module deliberately knows nothing about HTML, CSS, or tactical intent.
It turns an evidence bundle's event-compressed equipment stream into a small,
JSON-safe contract that a replay UI can render at any playback second.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd


_TIMELINE_COLUMNS = [
    "round", "tick", "seconds", "player", "team", "side", "inventory",
    "current_equip_value", "armor", "has_helmet", "has_defuser", "account",
]
_PAYLOAD_COLUMNS = [
    "seconds", "tick", "player", "team", "side", "inventory",
    "current_equip_value", "armor", "has_helmet", "has_defuser", "freeze_account",
]


def _empty_timeline() -> pd.DataFrame:
    return pd.DataFrame(columns=[*_TIMELINE_COLUMNS, "freeze_account"])


def round_loadout_timeline(loadout_events: pd.DataFrame, round_num: int) -> pd.DataFrame:
    """Return one round's ordered events with an immutable freeze-end balance.

    The first retained event per player is their freeze-end baseline.  Later
    rows carry the latest visible equipment state, while ``freeze_account``
    stays anchored to that first row even if a parser exposes later account
    changes.  This keeps the UI honest: equipment can be live, money is only
    the round-start audit context.
    """
    if loadout_events.empty or not set(_TIMELINE_COLUMNS).issubset(loadout_events.columns):
        return _empty_timeline()
    rows = loadout_events.loc[loadout_events["round"] == int(round_num), _TIMELINE_COLUMNS].copy()
    if rows.empty:
        return _empty_timeline()
    rows["seconds"] = pd.to_numeric(rows["seconds"], errors="coerce")
    rows["tick"] = pd.to_numeric(rows["tick"], errors="coerce")
    rows = rows.dropna(subset=["seconds", "tick", "player", "team"])
    if rows.empty:
        return _empty_timeline()
    rows["player"] = rows["player"].astype(str)
    rows["team"] = rows["team"].astype(str)
    rows["side"] = rows["side"].fillna("").astype(str).str.upper()
    rows = rows.sort_values(["seconds", "tick", "player"], kind="stable").reset_index(drop=True)
    baselines = (
        rows.drop_duplicates("player", keep="first")[["player", "account"]]
        .rename(columns={"account": "freeze_account"})
    )
    return rows.merge(baselines, on="player", how="left", validate="many_to_one")


def loadout_state_at(
    loadout_events: pd.DataFrame, round_num: int, elapsed_second: float,
) -> pd.DataFrame:
    """Return each player's last recorded visible state at a playback second."""
    timeline = round_loadout_timeline(loadout_events, round_num)
    if timeline.empty:
        return pd.DataFrame(columns=_PAYLOAD_COLUMNS)
    cutoff = max(0.0, float(elapsed_second))
    observed = timeline.loc[timeline["seconds"] <= cutoff]
    if observed.empty:
        return pd.DataFrame(columns=_PAYLOAD_COLUMNS)
    latest = observed.groupby("player", sort=False, group_keys=False).tail(1).copy()
    return latest.sort_values(["team", "side", "player"], kind="stable").reset_index(drop=True)


def _inventory_items(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def _number_or_none(value: object) -> int | float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def _bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False if pd.isna(value) else bool(value)


def loadout_payload_for_round(loadout_events: pd.DataFrame, round_num: int) -> dict[str, Any]:
    """Build a JSON-safe V3.2 contract for the browser playback loop.

    The browser receives the event stream, not a fake static lineup. It can
    select each player's last event at its current playback time without a
    Streamlit rerun.  The payload is purposely unavailable for normal replay
    callers; ``app.py`` only exposes it to evidence bundles.
    """
    timeline = round_loadout_timeline(loadout_events, round_num)
    events: list[dict[str, Any]] = []
    for row in timeline.itertuples(index=False):
        events.append({
            "seconds": round(float(row.seconds), 3),
            "tick": int(row.tick),
            "player": str(row.player),
            "team": str(row.team),
            "side": str(row.side),
            "inventory": _inventory_items(row.inventory),
            "current_equip_value": _number_or_none(row.current_equip_value),
            "armor": _number_or_none(row.armor),
            "has_helmet": _bool(row.has_helmet),
            "has_defuser": _bool(row.has_defuser),
            "freeze_account": _number_or_none(row.freeze_account),
        })
    return {"available": bool(events), "round": int(round_num), "events": events}
