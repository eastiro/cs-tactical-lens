import pandas as pd

from src.sample_match import build_sample_match
from src.utility_efficiency import utility_efficiency_summary, utility_outcomes


def test_utility_outcomes_keep_only_direct_event_fields():
    data = build_sample_match()
    target = data.grenades.iloc[0]
    data.grenades.loc[data.grenades.index[0], "grenade_type"] = "he"
    data.grenades.loc[data.grenades.index[0], "land_seconds"] = float(target["seconds"]) + 1
    object.__setattr__(
        data,
        "damages",
        pd.DataFrame(
            [
                {
                    "round": int(target["round"]),
                    "seconds": float(target["seconds"]) + 1,
                    "attacker": target["thrower"],
                    "victim": "opponent",
                    "attacker_team": target["team"],
                    "victim_team": data.team_b,
                    "weapon": "hegrenade",
                    "damage_health": 42,
                }
            ]
        ),
    )

    outcomes = utility_outcomes(data)
    result = outcomes.loc[outcomes["grenade_id"] == 0].iloc[0]
    assert result.damage_health == 42
    assert {
        "team_kills_8s", "entry_followup_8s", "plant_followup_15s", "round_won"
    }.isdisjoint(outcomes.columns)


def test_flash_assist_is_assigned_to_latest_matching_flash():
    data = build_sample_match()
    grenade = data.grenades.iloc[1]
    data.grenades.loc[data.grenades.index[1], "grenade_type"] = "flash"
    data.grenades.loc[data.grenades.index[1], "land_seconds"] = float(grenade["seconds"]) + 1
    data.kills.loc[data.kills.index[0], "assister"] = grenade["thrower"]
    data.kills.loc[data.kills.index[0], "assisted_flash"] = True
    data.kills.loc[data.kills.index[0], "seconds"] = float(grenade["seconds"]) + 2

    outcomes = utility_outcomes(data)
    assert outcomes["flash_assists"].sum() == 1


def test_summary_excludes_smoke_and_win_rate_proxies():
    data = build_sample_match()
    data.grenades.loc[data.grenades.index[0], "grenade_type"] = "he"
    outcomes = utility_outcomes(data)
    summary = utility_efficiency_summary(outcomes)

    assert set(summary["grenade_type"]) <= {"he", "molotov", "flash"}
    assert "smoke" not in set(summary["grenade_type"])
    assert {
        "round_win_rate", "plant_followups", "kill_followups", "entry_followups"
    }.isdisjoint(summary.columns)
    assert (summary["direct_event_throws"] <= summary["throws"]).all()
