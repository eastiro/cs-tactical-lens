from pathlib import Path

import pandas as pd
import pytest

from src.awpy_adapter import load_normalized_bundle
from src.loadout_timeline import loadout_payload_for_round, loadout_state_at, round_loadout_timeline


def _events() -> pd.DataFrame:
    return pd.DataFrame([
        {"round": 1, "tick": 100, "seconds": 0.0, "player": "alpha", "team": "Falcons", "side": "T", "inventory": '["AK-47", "Smoke Grenade"]', "current_equip_value": 3500, "armor": 100, "has_helmet": True, "has_defuser": False, "account": 400},
        {"round": 1, "tick": 740, "seconds": 10.0, "player": "alpha", "team": "Falcons", "side": "T", "inventory": '["AK-47"]', "current_equip_value": 3200, "armor": 100, "has_helmet": True, "has_defuser": False, "account": 1500},
        {"round": 1, "tick": 100, "seconds": 0.0, "player": "bravo", "team": "Spirit", "side": "CT", "inventory": '["USP-S"]', "current_equip_value": 200, "armor": 0, "has_helmet": False, "has_defuser": True, "account": 800},
        {"round": 1, "tick": 1060, "seconds": 15.0, "player": "bravo", "team": "Spirit", "side": "CT", "inventory": '[]', "current_equip_value": 0, "armor": 0, "has_helmet": False, "has_defuser": False, "account": 800},
        {"round": 2, "tick": 100, "seconds": 0.0, "player": "alpha", "team": "Falcons", "side": "CT", "inventory": '["M4A1-S"]', "current_equip_value": 3100, "armor": 100, "has_helmet": True, "has_defuser": True, "account": 0},
    ])


def test_timeline_preserves_every_visible_change_and_freeze_balance():
    timeline = round_loadout_timeline(_events(), 1)

    assert timeline["seconds"].tolist() == [0.0, 0.0, 10.0, 15.0]
    assert timeline.loc[timeline["player"] == "alpha", "freeze_account"].tolist() == [400, 400]
    assert timeline.loc[timeline["player"] == "bravo", "freeze_account"].tolist() == [800, 800]


def test_state_at_uses_last_visible_event_without_making_money_live():
    state = loadout_state_at(_events(), 1, 12.0).set_index("player")

    assert state.loc["alpha", "inventory"] == '["AK-47"]'
    assert state.loc["bravo", "inventory"] == '["USP-S"]'
    assert state.loc["alpha", "freeze_account"] == 400

    after_death = loadout_state_at(_events(), 1, 15.0).set_index("player")
    assert after_death.loc["bravo", "inventory"] == "[]"
    assert not bool(after_death.loc["bravo", "has_defuser"])


def test_payload_is_json_safe_and_round_scoped():
    payload = loadout_payload_for_round(_events(), 1)

    assert payload["available"]
    assert payload["round"] == 1
    assert len(payload["events"]) == 4
    alpha_change = next(item for item in payload["events"] if item["player"] == "alpha" and item["seconds"] == 10.0)
    assert alpha_change["inventory"] == ["AK-47"]
    assert alpha_change["freeze_account"] == 400


def test_real_falcons_bundle_exposes_a_ten_player_evidence_timeline():
    bundle = Path(
        "data/processed/falcons-2026-karrigan/"
        "cs-asia-championships-2026-falcons-vs-legacy/de_mirage"
    )
    if not (bundle / "metadata.json").is_file():
        pytest.skip(
            "需要本地完整语料（data/processed/falcons-2026-karrigan/…/de_mirage）。"
            "公开仓库只附带 data/showcase 轻量包。"
        )
    data = load_normalized_bundle(bundle)
    payload = loadout_payload_for_round(data.loadout_events, 1)

    assert payload["available"]
    assert {item["player"] for item in payload["events"] if item["seconds"] == 0} == {
        "NiKo", "TeSeS", "karrigan", "kyousuke", "m0NESY",
        "arT", "dumau", "latto", "n1ssim", "saadzin",
    }
    assert all("freeze_account" in item for item in payload["events"])
