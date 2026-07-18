from pathlib import Path

import pytest

from src.awpy_adapter import load_normalized_bundle
from src.tactics import AREA_GROUP, AREA_LABEL, build_tactical_findings, opening_contact_evidence


BUNDLE = Path("data/processed/furia-falcons-mirage")


@pytest.mark.skipif(not (BUNDLE / "metadata.json").exists(), reason="本地真实案例尚未导入")
def test_falcons_furia_case_is_bound_to_verified_result():
    data = load_normalized_bundle(BUNDLE)
    final = data.rounds.iloc[-1]

    assert data.team_a == "Team Falcons"
    assert data.team_b == "FURIA"
    assert (int(final.team_a_score), int(final.team_b_score)) == (13, 8)
    assert final.winner == "Team Falcons"
    assert len(data.rounds) == 21
    assert set(data.positions.side) == {"T", "CT"}
    assert set(data.positions["area"].dropna()) <= set(AREA_LABEL)
    assert AREA_LABEL["TRamp"] == "A1"
    assert AREA_LABEL["PalaceInterior"] == "A2（二楼）"
    assert AREA_LABEL["Apartments"] == "B 二楼"
    assert AREA_LABEL["Catwalk"] == "B 小"
    assert AREA_LABEL["SnipersNest"] == "狙击房（Sniper's Nest，俗称 VIP）"
    assert AREA_LABEL["Connector"] == "拱门"
    assert AREA_LABEL["Ladder"] == "黑屋"
    assert AREA_LABEL["Shop"] == "超市"
    assert AREA_LABEL["CTSpawn"] == "警家"
    assert AREA_GROUP["Scaffolding"] == "A"
    assert AREA_GROUP["Jungle"] == "A"
    assert AREA_GROUP["SideAlley"] == "B"
    assert AREA_GROUP["Truck"] == "B"
    assert set(data.grenades.grenade_type) <= {"smoke", "flash", "molotov", "he", "decoy"}
    assert not data.grenades[["seconds", "x", "y"]].isna().any().any()
    assert data.metadata["tickrate"] == 64
    assert len(data.damages) == 491
    assert len(data.bomb_events) == 132
    assert int(data.kills["assisted_flash"].fillna(False).sum()) == 7
    assert {"hegrenade", "inferno"} <= set(data.damages["weapon"].dropna())
    first_round = data.rounds.loc[data.rounds["round"] == 1].iloc[0]
    assert (first_round["end"] - first_round["freeze_end"]) / 64 == pytest.approx(43.234375)
    assert data.kills.loc[data.kills["round"] == 1, "seconds"].max() == pytest.approx(43.234375)
    assert data.grenades["trajectory"].str.startswith("[[").all()
    findings = build_tactical_findings(data, "Team Falcons")
    assert len(findings) == 1
    assert findings[0].kind == "entry_conversion"
    assert "本场结果统计" in findings[0].summary
    assert all(finding.evidence for finding in findings)
    contact = opening_contact_evidence(data, "Team Falcons", "CT")
    assert len(contact) == 12
    assert {"本队", "对手"} <= set(contact["first_kill_for"])
    assert contact["seconds"].between(0, 120).all()
    assert contact["team_alive_after_5s"].notna().any()
