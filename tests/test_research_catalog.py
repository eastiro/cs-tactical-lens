"""Tests for series discovery and profile-scoped replay provenance."""

from __future__ import annotations

import json

import pandas as pd

from src.research_catalog import (
    discover_research_profiles,
    evidence_bundle_index,
    load_profile_artifacts,
    maps_with_pairable_profiles,
    opponent_profiles,
    profiles_for_map,
)


def _write_profile(root, profile_id, *, team, map_name="de_mirage", matches=None):
    manifest = root / f"{profile_id}.json"
    series_dir = root / profile_id
    series_dir.mkdir()
    (series_dir / "series_metadata.json").write_text(
        json.dumps({"match_count": 4, "eligible_precontact_samples": 37}),
        encoding="utf-8",
    )
    pd.DataFrame([{"match_id": "m1", "side": "T"}]).to_csv(
        series_dir / "precontact_opening_samples.csv", index=False
    )
    pd.DataFrame([{"formation": "2-1-2", "sample_count": 1}]).to_csv(
        series_dir / "precontact_opening_profile.csv", index=False
    )
    manifest.write_text(
        json.dumps(
            {
                "team": team,
                "map": map_name,
                "season": "test roster",
                "matches": matches or [],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_discovery_requires_complete_artifacts_and_ignores_examples(tmp_path):
    _write_profile(tmp_path, "spirit-mirage", team="Team Spirit")
    _write_profile(tmp_path, "falcons-inferno", team="Team Falcons", map_name="de_inferno")
    (tmp_path / "incomplete-mirage.json").write_text(
        json.dumps({"team": "Incomplete", "map": "de_mirage"}), encoding="utf-8"
    )
    (tmp_path / "demo.example.json").write_text(
        json.dumps({"team": "Example", "map": "de_mirage"}), encoding="utf-8"
    )

    profiles = discover_research_profiles(tmp_path)

    assert [(profile.map_name, profile.team) for profile in profiles] == [
        ("de_inferno", "Team Falcons"),
        ("de_mirage", "Team Spirit"),
    ]
    assert profiles[1].match_count == 4
    assert profiles[1].eligible_samples == 37


def test_pairable_maps_and_opponents_are_map_and_team_scoped(tmp_path):
    _write_profile(tmp_path, "falcons-mirage", team="Team Falcons")
    _write_profile(tmp_path, "spirit-mirage", team="Team Spirit")
    _write_profile(tmp_path, "spirit-inferno", team="Team Spirit", map_name="de_inferno")

    profiles = discover_research_profiles(tmp_path)
    mirage = profiles_for_map(profiles, "DE_MIRAGE")

    assert maps_with_pairable_profiles(profiles) == ("de_mirage",)
    assert [profile.profile_id for profile in mirage] == ["falcons-mirage", "spirit-mirage"]
    assert [profile.team for profile in opponent_profiles(profiles, mirage[0])] == ["Team Spirit"]


def test_evidence_index_keeps_same_match_id_separate_per_profile(tmp_path):
    falcons_bundle = tmp_path / "processed" / "falcons" / "de_mirage"
    spirit_bundle = tmp_path / "processed" / "spirit" / "de_mirage"
    falcons_bundle.mkdir(parents=True)
    spirit_bundle.mkdir(parents=True)
    _write_profile(
        tmp_path,
        "falcons-mirage",
        team="Team Falcons",
        matches=[{"id": "same-real-match", "bundle": "processed\\falcons\\de_mirage"}],
    )
    _write_profile(
        tmp_path,
        "spirit-mirage",
        team="Team Spirit",
        matches=[{"id": "same-real-match", "bundle": "processed/spirit/de_mirage"}],
    )

    profiles = discover_research_profiles(tmp_path)
    index = evidence_bundle_index(profiles)

    assert index[("falcons-mirage", "same-real-match")] == falcons_bundle.resolve()
    assert index[("spirit-mirage", "same-real-match")] == spirit_bundle.resolve()


def test_profile_artifacts_load_without_reparsing_demos(tmp_path):
    _write_profile(tmp_path, "spirit-mirage", team="Team Spirit")
    profile = discover_research_profiles(tmp_path)[0]

    metadata, samples, opening = load_profile_artifacts(profile)

    assert metadata["match_count"] == 4
    assert samples["match_id"].tolist() == ["m1"]
    assert opening["formation"].tolist() == ["2-1-2"]
