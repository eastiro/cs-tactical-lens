from __future__ import annotations

import pandas as pd

from src.economy import classify_player_loadout, classify_team_economy, normalise_inventory


def _team(*inventories: list[str], armor: int = 100, **extra) -> pd.DataFrame:
    rows = []
    for index, inventory in enumerate(inventories, start=1):
        rows.append({
            "player": f"p{index}",
            "team": "Team Falcons",
            "side": "T",
            "inventory": inventory,
            "armor": armor,
            "current_equip_value": extra.get("equip", 4500),
            **{key: value for key, value in extra.items() if key in {"start_cash", "cash_after_buy", "cash_spent"}},
        })
    return pd.DataFrame(rows)


def test_inventory_normalisation_accepts_awpy_and_csv_values() -> None:
    assert normalise_inventory(["Karambit", "AK-47"]) == ("karambit", "ak-47")
    assert normalise_inventory('["Glock-18", "Smoke Grenade"]') == ("glock-18", "smoke grenade")


def test_player_loadout_ignores_knife_c4_and_grenades() -> None:
    result = classify_player_loadout({
        "player": "p1",
        "inventory": ["Karambit", "AK-47", "C4", "Smoke Grenade"],
        "armor": 100,
    })
    assert result["loadout"] == "rifle"
    assert result["utility_count"] == 1


def test_pistol_round_is_separate_from_eco() -> None:
    result = classify_team_economy(_team(*([["Glock-18"]] * 5), armor=0), pistol_round=True)
    assert result["label"] == "pistol"


def test_full_buy_requires_team_level_rifles_and_armor() -> None:
    result = classify_team_economy(_team(*([["AK-47", "Smoke Grenade"]] * 5)))
    assert result["label"] == "full_buy"


def test_mixed_is_not_called_half_buy_when_one_player_has_a_saved_rifle() -> None:
    result = classify_team_economy(_team(
        ["AK-47"], ["Glock-18"], ["Glock-18"], ["Glock-18"], ["Glock-18"],
        equip=1500,
    ))
    assert result["label"] == "mixed"


def test_force_buy_requires_low_remaining_cash_and_weapon_commitment() -> None:
    result = classify_team_economy(_team(
        *([["Galil AR", "Smoke Grenade"]] * 5),
        equip=3000,
        cash_after_buy=100,
    ))
    # A low-cost primary weapon plus very little freeze-end cash is a force.
    assert result["label"] == "force_buy"


def test_partial_buy_with_cash_left_is_not_forced_from_unreliable_spend_fields() -> None:
    result = classify_team_economy(_team(
        *([["Galil AR", "Smoke Grenade"]] * 5),
        equip=3000,
        cash_after_buy=2200,
        start_cash=100,
        cash_spent=20000,
    ))
    assert result["label"] == "half_buy"


def test_low_loadout_without_cash_evidence_stays_conservative() -> None:
    result = classify_team_economy(_team(
        ["Desert Eagle"], ["Desert Eagle"], ["Glock-18"], ["Glock-18"], ["Glock-18"],
        equip=1800,
    ))
    assert result["label"] in {"eco", "half_buy", "unknown"}
