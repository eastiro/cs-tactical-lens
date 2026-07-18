import json
from dataclasses import replace

import pandas as pd
import pytest

from src.awpy_adapter import write_normalized_bundle
from src.sample_match import build_sample_match
from src.team_map_series import (
    ECONOMY_SAMPLE_SECONDS,
    load_team_map_series,
    opening_profile,
    precontact_opening_samples,
    sample_second_for_economy,
    series_evidence_summary,
)


def _write_manifest(tmp_path, data, *, map_name=None):
    bundle = write_normalized_bundle(data, tmp_path / "bundle")
    manifest = tmp_path / "series.json"
    manifest.write_text(
        json.dumps(
            {
                "team": data.team_a,
                "map": data.map_name if map_name is None else map_name,
                "season": "test",
                "matches": [
                    {
                        "id": "match-1",
                        "bundle": str(bundle),
                        "opponent": data.team_b,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_series_manifest_requires_the_declared_team_and_map(tmp_path):
    data = build_sample_match()
    manifest = _write_manifest(tmp_path, data, map_name="de_inferno")

    with pytest.raises(ValueError, match="清单要求 de_inferno"):
        load_team_map_series(manifest)


def test_precontact_samples_exclude_rounds_where_contact_already_started(tmp_path):
    data = build_sample_match()
    early_round = int(data.kills.iloc[0]["round"])
    data.kills.loc[data.kills["round"] == early_round, "seconds"] = 5.0
    series = load_team_map_series(_write_manifest(tmp_path, data))

    samples = precontact_opening_samples(series, sample_second=20.0)
    early = samples.loc[samples["round"] == early_round].iloc[0]

    assert not bool(early["sample_eligible"])
    assert early["exclusion_reason"] == "contact_before_sample"
    assert set(samples["economy_scope"]) == {"unclassified"}
    assert set(samples["economy_label"]) == {"unknown"}
    assert samples.loc[samples["sample_eligible"], "formation"].str.contains("匪家|警家").all()


def test_opening_profile_is_only_built_from_eligible_samples(tmp_path):
    data = build_sample_match()
    series = load_team_map_series(_write_manifest(tmp_path, data))
    samples = precontact_opening_samples(series, sample_second=20.0)
    profile = opening_profile(samples)

    assert not profile.empty
    assert profile["sample_count"].sum() == int(samples["sample_eligible"].sum())
    assert profile["sample_share"].between(0, 1).all()
    assert all(profile["match_count"] == 1)


def test_series_evidence_summary_reports_scope_without_inference(tmp_path):
    data = build_sample_match()
    series = load_team_map_series(_write_manifest(tmp_path, data))
    samples = precontact_opening_samples(series, sample_second=20.0)
    profile = opening_profile(samples)

    summary = series_evidence_summary(samples, profile, "T")
    t_samples = samples.loc[samples["side"] == "T"]

    assert summary["side"] == "T"
    assert summary["total_rounds"] == len(t_samples)
    assert summary["eligible_samples"] == int(t_samples["sample_eligible"].sum())
    assert summary["coverage_matches"] == 1
    assert summary["unique_formations"] >= 1
    assert summary["median_contact_second"] is not None
    assert summary["top_formation_count"] >= 1


def test_economy_labels_select_documented_observation_checkpoints(tmp_path):
    data = build_sample_match()
    team = data.team_a
    players = data.positions.loc[data.positions["team"] == team, "player"].drop_duplicates().tolist()

    def snapshots(round_num, inventory, *, cash_after_buy=2000, equip=3000):
        return [
            {
                "round": round_num,
                "tick": round_num * 100,
                "player": player,
                "team": team,
                "side": "T",
                "seconds": 0.0,
                "inventory": inventory,
                "armor": 100,
                "has_helmet": True,
                "has_defuser": False,
                "current_equip_value": equip,
                "cash_after_buy": cash_after_buy,
                "start_cash": 0,
                "cash_spent": 0,
            }
            for player in players
        ]

    # Round 1 is pistol by definition. R2 is half-buy, R3 force-buy and R4
    # full-buy. Remaining snapshot-free rounds retain the 20-second fallback.
    economy_rows = []
    economy_rows += snapshots(1, ["Glock-18"], cash_after_buy=0)
    economy_rows += snapshots(2, ["Galil AR"], cash_after_buy=2200)
    economy_rows += snapshots(3, ["Galil AR"], cash_after_buy=100)
    economy_rows += snapshots(4, ["AK-47", "Smoke Grenade"], cash_after_buy=100, equip=4500)
    data = replace(data, economy_snapshots=pd.DataFrame(economy_rows))
    series = load_team_map_series(_write_manifest(tmp_path, data))

    samples = precontact_opening_samples(series, sample_second=20.0)
    t_samples = samples.loc[samples["side"].eq("T")].set_index("round")

    assert t_samples.loc[1, "economy_label"] == "pistol"
    assert t_samples.loc[1, "sample_second"] == 15.0
    assert t_samples.loc[2, "economy_label"] == "half_buy"
    assert t_samples.loc[2, "sample_second"] == 12.0
    assert t_samples.loc[3, "economy_label"] == "force_buy"
    assert t_samples.loc[3, "sample_second"] == 15.0
    assert t_samples.loc[4, "economy_label"] == "full_buy"
    assert t_samples.loc[4, "sample_second"] == 20.0
    assert t_samples.loc[5, "economy_label"] == "unknown"
    assert t_samples.loc[5, "sample_second"] == 20.0
    assert sample_second_for_economy("eco") == 15.0
    assert sample_second_for_economy("mixed") == 20.0
    assert ECONOMY_SAMPLE_SECONDS == {
        "full_buy": 20.0,
        "pistol": 15.0,
        "half_buy": 12.0,
        "force_buy": 15.0,
        "eco": 15.0,
    }
