"""Regression tests for team validation with incomplete official demo summaries."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_match_archives import _canonicalize_team_names, _observed_team_names, _validate

from src.schema import MatchData


def _demo_with_missing_summary_team() -> MatchData:
    return MatchData(
        match_name="Falcons vs 9z",
        map_name="de_dust2",
        team_a="Team Falcons",
        team_b="None",
        source_kind="demo",
        rounds=pd.DataFrame([{"round": 1, "winner": "Team Falcons", "winning_side": "CT", "team_a_score": 1, "team_b_score": 0}]),
        kills=pd.DataFrame([{"round": 1, "attacker": "karrigan", "victim": "dgt", "attacker_team": "Team Falcons", "attacker_side": "CT", "x": 0, "y": 0, "seconds": 15, "is_first_kill": True}]),
        positions=pd.DataFrame([
            {"round": 1, "player": player, "team": "Team Falcons", "side": "CT", "seconds": 15, "x": 0, "y": 0, "area": "A"}
            for player in ("karrigan", "NiKo", "TeSeS", "m0NESY", "kyousuke")
        ] + [{"round": 1, "player": "dgt", "team": "9z Globant", "side": "T", "seconds": 15, "x": 1, "y": 1, "area": "B"}]),
        grenades=pd.DataFrame(columns=["round", "thrower", "team", "grenade_type", "seconds", "x", "y"]),
    )


def test_event_tables_restore_missing_summary_team_for_validation() -> None:
    data = _demo_with_missing_summary_team()
    registry = {"teams": ["Team Falcons", "9z"]}

    assert _observed_team_names(data) == ["9z Globant", "Team Falcons"]
    _validate(
        data,
        {"map": "de_dust2"},
        registry,
        "Team Falcons",
        {"karrigan", "NiKo", "TeSeS", "m0NESY", "kyousuke"},
    )


def test_canonicalizer_maps_event_table_team_when_summary_is_missing() -> None:
    canonical = _canonicalize_team_names(
        _demo_with_missing_summary_team(),
        {"teams": ["Team Falcons", "9z"]},
    )
    assert canonical.team_a == "Team Falcons"
    assert canonical.team_b == "9z"
    assert set(canonical.positions["team"]) == {"Team Falcons", "9z"}
