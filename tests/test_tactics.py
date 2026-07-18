from src.sample_match import build_sample_match
from src.tactics import (
    build_tactical_findings,
    default_formation_summary,
    default_shape_summary,
    grenades_for_side,
    position_shapes,
    round_routes,
    rounds_for_side,
    shape_timeline,
    shape_transitions,
    t_entry_results,
)


def test_rounds_for_side_uses_observed_team_assignments():
    data = build_sample_match()
    assert rounds_for_side(data, data.team_a, "T")
    assert set(rounds_for_side(data, data.team_a, "T")).isdisjoint(rounds_for_side(data, data.team_a, "CT"))


def test_grenades_for_side_changes_with_side_selection():
    data = build_sample_match()
    team = data.team_a
    t_grenades = grenades_for_side(data, team, "T")
    ct_grenades = grenades_for_side(data, team, "CT")

    assert not t_grenades.empty
    assert not ct_grenades.empty
    assert set(t_grenades["round"]).isdisjoint(set(ct_grenades["round"]))


def test_shape_does_not_reuse_ended_round_at_later_sample():
    data = build_sample_match()
    short_round = rounds_for_side(data, data.team_a, "T")[0]
    shortened = data.positions.loc[~((data.positions["round"] == short_round) & (data.positions["seconds"] > 20))].copy()
    object.__setattr__(data, "positions", shortened)
    shapes = position_shapes(data, data.team_a, "T", 40)
    assert short_round not in set(shapes["round"])


def test_backfield_can_be_the_actual_dominant_zone():
    data = build_sample_match()
    team = data.team_a
    side = "T"
    round_num = rounds_for_side(data, team, side)[0]
    positions = data.positions.copy()
    positions.loc[
        (positions["round"] == round_num)
        & (positions["team"] == team)
        & (positions["side"] == side)
        & (positions["seconds"] <= 20),
        "area",
    ] = "TSpawn"
    object.__setattr__(data, "positions", positions)

    shapes = position_shapes(data, team, side, 20)
    dominant = shapes.loc[shapes["round"] == round_num, "dominant_zone"].item()
    assert dominant == "OTHER"


def test_shape_timeline_keeps_checkpoints_and_traceable_rounds():
    data = build_sample_match()
    timeline = shape_timeline(data, data.team_a, "T", (20, 50, 80))
    transitions = shape_transitions(data, data.team_a, "T", (20, 50, 80))

    assert set(timeline["seconds"]) == {20.0, 50.0, 80.0}
    assert not transitions.empty
    assert transitions["count"].sum() == len(rounds_for_side(data, data.team_a, "T"))
    assert all(len(rounds) >= 1 for rounds in transitions["rounds"])


def test_round_routes_keep_ended_rounds_as_missing_checkpoints():
    data = build_sample_match()
    team = data.team_a
    side = "T"
    short_round = rounds_for_side(data, team, side)[0]
    shortened = data.positions.loc[
        ~((data.positions["round"] == short_round) & (data.positions["seconds"] > 20))
    ].copy()
    object.__setattr__(data, "positions", shortened)

    routes = round_routes(data, team, side, (20, 40, 60))
    short_route = routes.loc[routes["round"] == short_round]

    assert len(short_route) == 3
    assert short_route.loc[short_route["seconds"] == 20, "available"].item()
    assert not short_route.loc[short_route["seconds"] == 40, "available"].item()
    assert not short_route["complete_route"].any()
    assert short_route["sequence"].isna().all()


def test_round_routes_sequence_matches_transition_groups():
    data = build_sample_match()
    team = data.team_a
    routes = round_routes(data, team, "T", (20, 50, 80))
    transitions = shape_transitions(data, team, "T", (20, 50, 80))

    complete = routes.loc[routes["complete_route"], ["round", "sequence"]].drop_duplicates()
    assert len(complete) == len(rounds_for_side(data, team, "T"))
    assert complete["sequence"].notna().all()
    assert set(complete["sequence"]) == set(transitions["sequence"])


def test_default_shape_summary_compares_both_sides():
    data = build_sample_match()
    summary = default_shape_summary(data, data.team_a, 20)

    assert set(summary["side"]) == {"T", "CT"}
    assert (summary["valid_rounds"] > 0).all()
    assert summary["share"].between(0, 1).all()
    assert all(len(rounds) == count for rounds, count in zip(summary["rounds"], summary["count"], strict=True))


def test_default_formation_summary_requires_actual_repetition():
    data = build_sample_match()
    summary = default_formation_summary(data, data.team_a, 20)

    assert set(summary["side"]) == {"T", "CT"}
    assert summary["formation"].str.match(r"A\d+·B\d+·中\d+·(?:匪家|警家)\d+").all()
    assert (summary["is_repeated"] == (summary["count"] >= 2)).all()
    assert all(
        len(rounds) == count
        for rounds, count in zip(summary["rounds"], summary["count"], strict=True)
    )


def test_t_entry_results_do_not_embed_post_entry_position_proxies():
    data = build_sample_match()
    results = t_entry_results(data, data.team_a)

    assert {"round", "first_kill_seconds", "earned_entry", "won_round"} <= set(results.columns)
    assert {"followup_zone", "bomb_site", "followup_seconds"}.isdisjoint(results.columns)


def test_findings_always_include_replay_evidence():
    data = build_sample_match()
    findings = build_tactical_findings(data, data.team_a)
    assert findings
    assert all(finding.evidence for finding in findings)
    assert all(item.round_num >= 1 and item.second >= 0 for finding in findings for item in finding.evidence)
