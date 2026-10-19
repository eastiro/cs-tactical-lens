"""Tests for the event feed (event_rows in app.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest


# ── Mock Streamlit only while importing app (restore afterwards) ──
class _CacheData:
    """Mimics st.cache_data: both @st.cache_data and @st.cache_data(k=v)."""

    def __call__(self, *args: object, **kw: object) -> object:
        if args and callable(args[0]):
            return args[0]  # bare decorator
        return lambda f: f  # decorator factory


_st_mock = MagicMock()
_st_mock.cache_data = _CacheData()
_st_mock.session_state = {}

import sys
from unittest.mock import patch

with patch.dict("sys.modules", {"streamlit": _st_mock}, clear=False):
    from app import event_rows

from src.sample_match import PLAYERS_A, TEAM_A, build_sample_match
from src.schema import MatchData

# ── Helpers ──


def _allow_fractional_coords(data: MatchData) -> None:
    """Ensure grenade coordinate columns are float64 for distance calculation."""
    data.grenades["x"] = data.grenades["x"].astype("float64")
    data.grenades["y"] = data.grenades["y"].astype("float64")


def _make_data_with_named_smoke() -> MatchData:
    """Return a synthetic MatchData with a named smoke and a bomb event in round 1."""
    data = build_sample_match()
    _allow_fractional_coords(data)

    # Make the first grenade a smoke landing near "Connector" (→ "拱门烟")
    smoke_idx = data.grenades.index[0]
    data.grenades.loc[smoke_idx, "grenade_type"] = "smoke"
    data.grenades.loc[smoke_idx, "seconds"] = 15.0
    data.grenades.loc[smoke_idx, "land_seconds"] = 22.0
    data.grenades.loc[smoke_idx, "x"] = 50.0
    data.grenades.loc[smoke_idx, "y"] = 50.0

    # Change other round-1 smokes to flash so we have exactly 1 named smoke
    for idx in data.grenades.loc[data.grenades["round"] == 1].index:
        if idx == smoke_idx:
            continue
        dtype = str(data.grenades.loc[idx, "grenade_type"]).lower().replace("_", "").replace(" ", "")
        if dtype in {"smoke", "smokegrenade"}:
            data.grenades.loc[idx, "grenade_type"] = "flash"

    # Add a reference position at the same coordinates with a known Mirage area
    # (in-place on the existing DataFrame to avoid FrozenInstanceError)
    data.positions.loc[len(data.positions)] = [
        1, "ref", TEAM_A, "T", 30.0, 50.0, 50.0, "Connector",
    ]

    # Assign bomb_events via object.__setattr__ (field is frozen)
    bomb_df = pd.DataFrame(
        [
            {
                "round": 1,
                "tick": 0,
                "seconds": 35.0,
                "event": "plant",
                "player": PLAYERS_A[0],
                "team": TEAM_A,
                "bombsite": "A",
                "x": 75.0,
                "y": 70.0,
            }
        ]
    )
    object.__setattr__(data, "bomb_events", bomb_df)

    return data


# ── Tests ──


def test_event_rows_shows_named_smoke_by_default() -> None:
    """Named smoke should appear even when include_utility=False."""
    data = _make_data_with_named_smoke()
    events = event_rows(data, 1, second=60.0, include_utility=False)
    smokes = [e for e in events if e.get("kind") == "smoke"]
    assert len(smokes) == 1
    assert "拱门烟" in smokes[0]["body"]
    # No generic utility events when include_utility=False
    utils = [e for e in events if e.get("kind") == "utility"]
    assert len(utils) == 0


def test_event_rows_include_utility_no_duplicate_smoke() -> None:
    """include_utility=True should not duplicate named smoke as generic 烟雾弹."""
    data = _make_data_with_named_smoke()
    events = event_rows(data, 1, second=60.0, include_utility=True)
    smokes = [e for e in events if e.get("kind") == "smoke"]
    utils = [e for e in events if e.get("kind") == "utility"]
    # Named smoke is present
    assert len(smokes) == 1
    # No utility entry contains the named smoke's display_name
    for u in utils:
        assert "拱门烟" not in u["body"]
    # At least one generic utility remains (the non-smoke grenades from round 1)
    assert len(utils) >= 1


def test_event_rows_named_smoke_timing() -> None:
    """Named smoke only appears when second >= land_seconds."""
    data = _make_data_with_named_smoke()
    # Before land_seconds (lands at 22.0)
    events_before = event_rows(data, 1, second=20.0, include_utility=False)
    smokes_before = [e for e in events_before if e.get("kind") == "smoke"]
    assert len(smokes_before) == 0

    # At land_seconds
    events_at = event_rows(data, 1, second=22.0, include_utility=False)
    smokes_at = [e for e in events_at if e.get("kind") == "smoke"]
    assert len(smokes_at) == 1
    assert float(smokes_at[0]["seconds"]) == 22.0

    # After land_seconds
    events_after = event_rows(data, 1, second=60.0, include_utility=False)
    smokes_after = [e for e in events_after if e.get("kind") == "smoke"]
    assert len(smokes_after) == 1


def test_event_rows_bomb_events() -> None:
    """Bomb events appear in the feed with proper labels."""
    data = _make_data_with_named_smoke()
    events = event_rows(data, 1, second=60.0, include_utility=False)
    bombs = [e for e in events if e.get("kind") == "bomb"]
    assert len(bombs) >= 1
    assert any("下包" in b["body"] for b in bombs)


def test_event_rows_sorts_reverse_chronological() -> None:
    """All events sorted newest-first by seconds."""
    data = _make_data_with_named_smoke()
    events = event_rows(data, 1, second=60.0, include_utility=False)
    times = [float(e["seconds"]) for e in events]
    assert times == sorted(times, reverse=True), "events must be reverse-chronological"


def test_event_rows_no_bomb_events_does_not_error() -> None:
    """Empty bomb_events should not cause errors."""
    data = build_sample_match()
    _allow_fractional_coords(data)
    events = event_rows(data, 1, second=60.0, include_utility=False)
    bombs = [e for e in events if e.get("kind") == "bomb"]
    assert len(bombs) == 0
    # Kill events should still be present
    kills = [e for e in events if e.get("kind") == "kill"]
    assert len(kills) >= 1


def test_event_rows_bomb_events_without_optional_fields_does_not_error() -> None:
    """The normalized schema only requires round/event/seconds for bomb rows."""
    data = build_sample_match()
    minimal_bomb_df = pd.DataFrame(
        [{"round": 1, "seconds": 18.0, "event": "plant"}]
    )
    object.__setattr__(data, "bomb_events", minimal_bomb_df)

    events = event_rows(data, 1, second=60.0, include_utility=False)

    bombs = [e for e in events if e.get("kind") == "bomb"]
    assert len(bombs) == 1
    assert "下包" in bombs[0]["body"]


def test_event_rows_translates_c4_drop_and_pickup() -> None:
    """Raw bomb transfer events should be readable in the Chinese feed."""
    data = build_sample_match()
    bomb_df = pd.DataFrame(
        [
            {"round": 1, "seconds": 12.0, "event": "drop", "player": "Aster"},
            {"round": 1, "seconds": 14.0, "event": "pickup", "player": "Boreal"},
        ]
    )
    object.__setattr__(data, "bomb_events", bomb_df)

    events = event_rows(data, 1, second=60.0, include_utility=False)
    bomb_bodies = [e["body"] for e in events if e.get("kind") == "bomb"]

    assert any("丢下 C4" in body for body in bomb_bodies)
    assert any("捡起 C4" in body for body in bomb_bodies)
