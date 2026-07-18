from src.analytics import (
    build_report,
    clutch_summary,
    control_profile,
    control_snapshot,
    first_kill_summary,
    round_progression,
)
from src.awpy_adapter import _normalise_loadout_events, normalise_awpy_frames, write_normalized_bundle
from src.sample_match import TEAM_A, build_sample_match
import pandas as pd


def test_sample_score_is_a_complete_24_round_match():
    progress = round_progression(build_sample_match())
    assert len(progress) == 24
    assert progress.iloc[-1].team_a_score + progress.iloc[-1].team_b_score == 24


def test_first_kills_add_up_to_one_per_round():
    assert first_kill_summary(build_sample_match()).first_kills.sum() == 24


def test_control_profile_is_a_distribution():
    assert control_profile(build_sample_match(), TEAM_A, "T", 50).share.sum() == 1


def test_control_snapshot_does_not_reuse_a_stale_position():
    data = build_sample_match()
    player = data.positions.loc[
        (data.positions["team"] == TEAM_A) & (data.positions["side"] == "T"), "player"
    ].iat[0]
    filtered_positions = data.positions.loc[
        ~(
            (data.positions["team"] == TEAM_A)
            & (data.positions["side"] == "T")
            & (data.positions["player"] == player)
            & (data.positions["seconds"] == 50)
        )
    ].copy()
    object.__setattr__(data, "positions", filtered_positions)

    snapshot = control_snapshot(data, TEAM_A, "T", 50)
    assert player not in set(snapshot["player"])


def test_synthetic_report_does_not_claim_real_team_finding():
    assert "合成" in build_report(build_sample_match(), TEAM_A)[0]


def test_empty_clutch_result_keeps_a_renderable_schema():
    data = build_sample_match()
    data.kills.loc[:, "seconds"] = 10
    assert list(clutch_summary(data).columns) == ["team", "late_round_attempts", "converted", "conversion_rate"]


def test_awpy_frames_are_normalised_without_guessing_a_score(tmp_path):
    frames = {
        "rounds": pd.DataFrame({"round_num": [1, 2], "freeze_end": [100, 1000], "end": [900, 1800], "winner": ["TERRORIST", "CT"], "reason": ["TargetSaved", "CTWin"]}),
        "ticks": pd.DataFrame({
            "round_num": [1, 1, 1, 1, 2, 2, 2, 2], "tick": [200, 200, 300, 300, 1100, 1100, 1200, 1200],
            "name": ["a", "b", "c", "d", "a", "b", "c", "d"], "side": ["t", "t", "ct", "ct", "ct", "ct", "t", "t"],
            "team_clan_name": ["Falcons", "Falcons", "FURIA", "FURIA", "Falcons", "Falcons", "FURIA", "FURIA"],
            "X": [1, 2, 3, 4, 5, 6, 7, 8], "Y": [11, 12, 13, 14, 15, 16, 17, 18], "place": ["Mid"] * 8,
            "inventory": [["AK-47", "Smoke Grenade"], ["M4A1-S"], ["Glock-18"], ["USP-S"]] * 2,
            "current_equip_value": [4500, 4000, 200, 200] * 2,
            "armor": [100, 100, 0, 0] * 2,
            "has_helmet": [True, True, False, False] * 2,
            "has_defuser": [False, True, False, False] * 2,
        }),
        "kills": pd.DataFrame({"round_num": [1, 2], "tick": [300, 1200], "attacker_name": ["a", "c"], "victim_name": ["c", "a"], "attacker_side": ["t", "t"], "victim_side": ["ct", "ct"], "attacker_X": [2, 7], "attacker_Y": [12, 17]}),
        "grenades": pd.DataFrame({"round_num": [1, 1, 2], "entity_id": [7, 7, 8], "thrower": ["a", "a", "c"], "grenade_type": ["CSmokeGrenadeProjectile", "CSmokeGrenadeProjectile", "CFlashbangProjectile"], "tick": [250, 280, 1150], "X": [2, 3, 7], "Y": [12, 13, 17]}),
    }
    data = normalise_awpy_frames(frames, map_name="de_mirage", match_name="FURIA vs Falcons")
    assert data.source_kind == "demo"
    assert data.rounds.iloc[-1].team_a_score + data.rounds.iloc[-1].team_b_score == 2
    assert data.rounds.team_a_score.tolist() == (data.rounds.winner == data.team_a).cumsum().tolist()
    assert data.rounds.team_b_score.tolist() == (data.rounds.winner == data.team_b).cumsum().tolist()
    assert data.kills.is_first_kill.sum() == 2
    assert len(data.grenades) == 2
    assert set(data.grenades.grenade_type) == {"smoke", "flash"}
    assert data.grenades.loc[data.grenades.grenade_type == "smoke", "x"].iat[0] == 3
    assert data.grenades.loc[data.grenades.grenade_type == "smoke", "land_seconds"].iat[0] == 180 / 64
    assert len(data.economy_snapshots) == 8
    assert data.economy_snapshots.loc[0, "inventory"] == '["AK-47", "Smoke Grenade"]'
    assert len(data.loadout_events) == 8
    bundle = write_normalized_bundle(data, tmp_path / "bundle")
    assert (bundle / "metadata.json").exists()
    assert (bundle / "loadout_events.csv").exists()


def test_loadout_events_keep_freeze_baseline_and_only_later_state_changes():
    raw_rounds = pd.DataFrame({"round_num": [1], "freeze_end": [100], "end": [300]})
    raw_ticks = pd.DataFrame({
        "round_num": [1, 1, 1, 1, 1],
        "tick": [90, 100, 130, 160, 180],
        "name": ["player", "player", "player", "player", "spectator"],
        "team_clan_name": ["Team", "Team", "Team", "Team", ""],
        "side": ["t", "t", "t", "t", ""],
        "inventory": [
            ["AK-47", "Smoke Grenade"],
            ["AK-47", "Smoke Grenade"],
            ["AK-47", "Smoke Grenade"],
            ["AK-47"],
            ["Knife"],
        ],
        # The 130 tick only changes bookkeeping values. It must not create a
        # visual sidebar update without a weapon, utility or armor change.
        "current_equip_value": [3500, 3500, 3600, 3200, 0],
        "cash": [500, 500, 1500, 1500, 0],
        "armor": [100, 100, 100, 100, 0],
        "has_helmet": [True, True, True, True, False],
        "has_defuser": [False] * 5,
    })

    events = _normalise_loadout_events(raw_ticks, raw_rounds)

    assert len(events) == 2
    assert events["tick"].tolist() == [100, 160]
    assert events["seconds"].tolist() == [0.0, 60 / 64]
    assert events["inventory"].tolist() == ['["AK-47", "Smoke Grenade"]', '["AK-47"]']
