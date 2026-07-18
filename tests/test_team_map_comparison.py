"""Tests for the descriptive V3 Falcons/Spirit comparison helpers."""

from __future__ import annotations

import pandas as pd

from src.team_map_comparison import (
    comparison_evidence,
    compare_opening_profiles,
    opening_profile_for_comparison,
)


def _samples() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"match_id": "a", "opponent": "X", "event": "E1", "date": "2026-01-01", "round": 1, "side": "T", "formation": "A2·B2·中1·匪家0", "sample_eligible": True, "contact_second": 30.0},
            {"match_id": "b", "opponent": "Y", "event": "E2", "date": "2026-01-02", "round": 2, "side": "T", "formation": "A2·B2·中1·匪家0", "sample_eligible": True, "contact_second": 40.0},
            {"match_id": "c", "opponent": "Z", "event": "E3", "date": "2026-01-03", "round": 3, "side": "T", "formation": "A1·B3·中1·匪家0", "sample_eligible": True, "contact_second": 25.0},
            {"match_id": "d", "opponent": "W", "event": "E4", "date": "2026-01-04", "round": 4, "side": "CT", "formation": "A3·B1·中1·警家0", "sample_eligible": True, "contact_second": 35.0},
            {"match_id": "e", "opponent": "W", "event": "E5", "date": "2026-01-05", "round": 5, "side": "T", "formation": "A9", "sample_eligible": False, "contact_second": 10.0},
        ]
    )


def test_profile_uses_only_eligible_side_samples() -> None:
    profile = opening_profile_for_comparison(_samples(), "T")
    assert profile.iloc[0]["sample_count"] == 2
    assert profile.iloc[0]["match_count"] == 2
    assert profile.iloc[0]["median_contact_second"] == 35.0
    assert profile.iloc[0]["opponents"] == ("X", "Y")


def test_profile_can_filter_economy_without_changing_default() -> None:
    samples = _samples()
    samples["economy_label"] = ["full_buy", "eco", "full_buy", "full_buy", "eco"]
    profile = opening_profile_for_comparison(samples, "T", economy="full_buy")
    assert int(profile["sample_count"].sum()) == 2


def test_evidence_can_filter_economy() -> None:
    samples = _samples()
    samples["economy_label"] = ["full_buy", "eco", "full_buy", "full_buy", "eco"]
    result = comparison_evidence(
        {"Team Falcons": samples}, "T", economy="eco"
    )
    assert len(result) == 1
    assert result.iloc[0]["round"] == 2


def test_profile_parses_string_boolean_flags() -> None:
    samples = _samples()
    samples["sample_eligible"] = samples["sample_eligible"].map(str)
    profile = opening_profile_for_comparison(samples, "T")
    assert int(profile["sample_count"].sum()) == 3


def test_comparison_has_union_and_delta() -> None:
    spirit = _samples().copy()
    spirit.loc[0, "formation"] = "A1·B3·中1·匪家0"
    result = compare_opening_profiles(
        {"Team Falcons": _samples(), "Team Spirit": spirit}, "T"
    )
    assert set(result["formation"]) == {"A1·B3·中1·匪家0", "A2·B2·中1·匪家0"}
    assert "sample_count_delta" in result.columns
    assert "share_delta" in result.columns


def test_comparison_empty_input_is_safe() -> None:
    result = compare_opening_profiles(
        {"Team Falcons": pd.DataFrame(), "Team Spirit": pd.DataFrame()}, "T"
    )
    assert result.empty
    assert list(result.columns) == ["formation"]


def test_evidence_includes_team_match_and_round() -> None:
    result = comparison_evidence(
        {"Team Falcons": _samples(), "Team Spirit": _samples()},
        "T",
        formation="A2·B2·中1·匪家0",
    )
    assert len(result) == 4
    assert set(["team", "match_id", "round", "contact_second"]).issubset(result.columns)


def test_evidence_can_filter_team_and_limit() -> None:
    result = comparison_evidence(
        {"Team Falcons": _samples(), "Team Spirit": _samples()},
        "T",
        team="Team Spirit",
        limit=1,
    )
    assert len(result) == 1
    assert result.iloc[0]["team"] == "Team Spirit"
