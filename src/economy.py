"""Auditable round-economy classification for CS2 demos.

The classifier deliberately separates what is observable at freeze end (the
loadout and remaining cash) from the stronger claim that a team intended to
save or force. A single saved rifle is not enough to call a team half-buy.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

ECONOMY_LABELS = (
    "pistol",
    "full_buy",
    "half_buy",
    "force_buy",
    "eco",
    "mixed",
    "unknown",
)

ECONOMY_LABEL_ZH = {
    "pistol": "手枪局",
    "full_buy": "全起",
    "half_buy": "半起",
    "force_buy": "刚枪",
    "eco": "经济局",
    "mixed": "混合 / 英雄枪",
    "unknown": "不确定",
}

_RIFLES = {
    "ak-47", "m4a1", "m4a1-s", "m4a4", "galil ar", "famas",
    "aug", "sg 553", "ssg 08", "scar-20", "g3sg1",
}
_SNIPERS = {"awp"}
_SMGS_SHOTGUNS = {
    "mac-10", "mp9", "mp7", "mp5-sd", "ump-45", "p90", "pp-bizon",
    "nova", "xm1014", "mag-7", "sawed-off",
}
_UPGRADED_PISTOLS = {
    "p250", "cz75-auto", "five-seven", "tec-9", "desert eagle", "r8 revolver",
}
_STARTER_PISTOLS = {"glock-18", "usp-s", "usp", "p2000", "dual berettas"}
_IGNORED_ITEMS = {
    "knife", "karambit", "m9 bayonet", "butterfly knife", "bayonet",
    "flip knife", "gut knife", "huntsman knife", "falchion knife",
    "shadow daggers", "navaja knife", "stiletto knife", "talon knife",
    "skeleton knife", "paracord knife", "survival knife", "nomad knife",
    "classic knife", "c4", "c4 explosive",
}
_GRENADE_WORDS = {
    "grenade", "flashbang", "smoke", "molotov", "incendiary", "hegrenade",
    "decoy", "breach charge", "fire bomb",
}


def _clean_item(value: Any) -> str:
    return " ".join(str(value).strip().lower().replace("_", "-").split())


def normalise_inventory(value: Any) -> tuple[str, ...]:
    """Return a stable tuple from Awpy lists or CSV-serialised lists."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(_clean_item(item) for item in value if str(item).strip())
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "[]"}:
        return ()
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
        if isinstance(parsed, (list, tuple, set)):
            return tuple(_clean_item(item) for item in parsed if str(item).strip())
    return ( _clean_item(text), )


def _weapon_tier(item: str) -> str | None:
    item = _clean_item(item)
    if not item or item in _IGNORED_ITEMS or any(word in item for word in _GRENADE_WORDS):
        return None
    if item in _RIFLES:
        return "rifle"
    if item in _SNIPERS:
        return "sniper"
    if item in _SMGS_SHOTGUNS:
        return "smg_shotgun"
    if item in _UPGRADED_PISTOLS:
        return "upgraded_pistol"
    if item in _STARTER_PISTOLS:
        return "starter_pistol"
    return "unknown_weapon"


def classify_player_loadout(row: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one freeze-end player snapshot without guessing intent."""
    inventory = normalise_inventory(row.get("inventory", row.get("weapons")))
    tiers = tuple(tier for item in inventory if (tier := _weapon_tier(item)))
    primary = next((tier for tier in tiers if tier in {"rifle", "sniper"}), None)
    known_tiers = {tier for tier in tiers if tier != "unknown_weapon"}
    if primary:
        loadout = primary
    elif "smg_shotgun" in known_tiers:
        loadout = "smg_shotgun"
    elif "upgraded_pistol" in known_tiers:
        loadout = "upgraded_pistol"
    elif "starter_pistol" in known_tiers:
        loadout = "starter_pistol"
    else:
        loadout = "unknown"
    try:
        equip_value = float(row.get("current_equip_value", row.get("freeze_end_equipment_value", float("nan"))))
    except (TypeError, ValueError):
        equip_value = float("nan")
    try:
        armor = float(row.get("armor", row.get("armor_value", 0)) or 0)
    except (TypeError, ValueError):
        armor = 0.0
    utility_count = sum(1 for item in inventory if any(word in item for word in _GRENADE_WORDS))
    return {
        "player": str(row.get("player", row.get("name", ""))),
        "team": str(row.get("team", "")),
        "side": str(row.get("side", "")).upper(),
        "loadout": loadout,
        "weapon_tiers": tiers,
        "inventory": inventory,
        "armor": armor,
        "armored": armor > 0,
        "has_helmet": bool(row.get("has_helmet", False)),
        "has_defuser": bool(row.get("has_defuser", False)),
        "utility_count": utility_count,
        "current_equip_value": equip_value,
    }


def _number(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(float("nan"), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def classify_team_economy(
    snapshots: pd.DataFrame | Iterable[Mapping[str, Any]],
    *,
    pistol_round: bool = False,
) -> dict[str, Any]:
    """Return one team-level label plus the evidence used to obtain it.

    ``force_buy`` is intentionally conservative: it requires a non-full
    loadout, multiple non-default weapons, and low remaining cash at freeze
    end. Some demo sources expose start/spend fields inconsistently, so those
    fields are retained for audit but are not classification inputs.
    """
    frame = snapshots.copy() if isinstance(snapshots, pd.DataFrame) else pd.DataFrame(list(snapshots))
    if frame.empty:
        return {"label": "unknown", "label_zh": ECONOMY_LABEL_ZH["unknown"], "confidence": "none", "reason": "没有冻结结束快照"}
    players = pd.DataFrame([classify_player_loadout(row) for row in frame.to_dict("records")])
    known = players[players["loadout"] != "unknown"]
    if pistol_round:
        label = "pistol"
        confidence = "high" if len(known) >= 4 else "medium"
        reason = "半场首回合按手枪局单独处理"
    elif len(known) < 4:
        label, confidence, reason = "unknown", "low", "冻结结束可识别选手不足 4 人"
    else:
        primary_count = int(players["loadout"].isin({"rifle", "sniper"}).sum())
        mid_count = int(players["loadout"].isin({"smg_shotgun", "upgraded_pistol"}).sum())
        starter_count = int((players["loadout"] == "starter_pistol").sum())
        armored_count = int(players["armored"].sum())
        equip_total = float(_number(players, "current_equip_value").sum(min_count=1))
        cash_after = float(_number(frame, "cash_after_buy").sum(min_count=1))
        cash_observations = int(_number(frame, "cash_after_buy").notna().sum())
        active_weapon_count = primary_count + mid_count
        force_evidence = (
            cash_observations >= 4
            and pd.notna(cash_after)
            and cash_after / max(len(frame), 1) <= 800
            and active_weapon_count >= 2
        )
        # HLTV's team-value shorthand uses roughly $20k as a full-buy signal;
        # keep it as a guardrail rather than requiring every grenade slot.
        if primary_count >= 4 and armored_count >= 4 and equip_total >= 20000:
            label, confidence, reason = "full_buy", "high", "至少 4 人有步枪/AWP 且至少 4 人有护甲"
        elif force_evidence and (primary_count < 4 or equip_total < 20000):
            label, confidence, reason = "force_buy", "medium", "未达全起且冻结结束剩余现金较低，队伍仍投入了非默认武器"
        elif primary_count in {1, 2} and starter_count >= 2:
            label, confidence, reason = "mixed", "medium", "少数选手有主武器，其余选手仍为低配"
        elif primary_count <= 1 and mid_count == 0 and starter_count >= 3:
            label, confidence, reason = "eco", "medium", "队伍大多数只有默认手枪，未见中高档主武器"
        elif (primary_count < 4 and (mid_count >= 2 or primary_count >= 2)) or (
            primary_count >= 4 and equip_total < 20000
        ):
            label, confidence, reason = "half_buy", "medium", "介于全起与 Eco 之间的中间装备结构"
        elif equip_total == 0 or pd.isna(equip_total):
            label, confidence, reason = "unknown", "low", "缺少可用装备价值"
        else:
            label, confidence, reason = "unknown", "low", "装备结构不足以区分半起、刚枪或混合购买"
    return {
        "label": label,
        "label_zh": ECONOMY_LABEL_ZH[label],
        "confidence": confidence,
        "reason": reason,
        "players": int(len(frame)),
        "known_players": int(len(known)),
    }
