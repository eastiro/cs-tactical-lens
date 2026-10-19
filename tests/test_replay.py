from src.replay import (
    entry_conversion_summary,
    movement_trails,
    position_snapshot,
    round_utility,
    score_after_round,
)
from src.sample_match import build_sample_match


def test_snapshot_keeps_one_player_position():
    data = build_sample_match()
    snapshot = position_snapshot(data, 1, 50)
    assert snapshot.player.nunique() == len(snapshot)
    assert len(snapshot) == 10


def test_trails_are_time_bounded():
    trails = movement_trails(build_sample_match(), 1, 50, lookback=30)
    assert trails.seconds.min() >= 20
    assert trails.seconds.max() <= 50


def test_entry_conversion_counts_all_rounds():
    summary = entry_conversion_summary(build_sample_match())
    assert summary.first_kills.sum() == 24


def test_utility_labels_are_human_readable_when_known():
    data = build_sample_match()
    data.grenades.loc[:, "grenade_type"] = "smoke"
    assert set(round_utility(data, 1).utility_label) == {"烟雾弹"}


def test_score_after_round_uses_bound_team_columns():
    assert sum(score_after_round(build_sample_match(), 24)) == 24
