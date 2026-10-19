from dataclasses import replace
from pathlib import Path

from conftest import requires_default_bundle

from src.awpy_adapter import load_normalized_bundle
from src.round_timeline import RoundTimelineEvent, build_round_timeline, survivor_curves

BUNDLE = Path("data/processed/furia-falcons-mirage")


def test_survivor_curves_decrement_the_victim_side():
    events = [
        RoundTimelineEvent(10, "kill", actor_side="T", victim_side="CT"),
        # A team kill still removes the victim from the actor's own side.
        RoundTimelineEvent(15, "kill", actor_side="T", victim_side="T"),
        RoundTimelineEvent(20, "kill", actor_side="CT", victim_side="T"),
    ]
    t_curve, ct_curve = survivor_curves(events, end_second=25)

    assert t_curve[-1] == (25.0, 3)
    assert ct_curve[-1] == (25.0, 4)


def test_survivor_curves_never_go_below_zero():
    event = RoundTimelineEvent(1, "kill", actor_side="CT", victim_side="T")
    events = [replace(event, seconds=second) for second in range(1, 8)]
    t_curve, _ = survivor_curves(events)

    assert min(alive for _, alive in t_curve) == 0


@requires_default_bundle
def test_real_round_uses_explicit_bomb_events():
    data = load_normalized_bundle(BUNDLE)
    events = build_round_timeline(data, 6)
    bomb_events = [event for event in events if event.kind != "kill"]

    assert [(event.kind, event.seconds) for event in bomb_events] == [
        ("plant", 68.453125),
        ("defuse", 80.34375),
    ]
    assert all(event.site == "B" for event in bomb_events)


@requires_default_bundle
def test_real_round_preserves_bomb_detonation():
    data = load_normalized_bundle(BUNDLE)
    bomb_events = [event for event in build_round_timeline(data, 15) if event.kind != "kill"]

    assert [(event.kind, event.seconds) for event in bomb_events] == [
        ("plant", 82.640625),
        ("detonate", 123.640625),
    ]


@requires_default_bundle
def test_real_kill_records_both_sides():
    data = load_normalized_bundle(BUNDLE)
    first = next(event for event in build_round_timeline(data, 1) if event.kind == "kill")

    assert (first.actor_side, first.victim_side) == ("CT", "T")
