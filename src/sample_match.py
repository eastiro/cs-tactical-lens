"""A deterministic, clearly labelled synthetic match for the first UI slice."""

import math

import pandas as pd

from .schema import MatchData

TEAM_A = "Astra"
TEAM_B = "Northstar"
PLAYERS_A = ["Aster", "Comet", "Iris", "Mako", "Rune"]
PLAYERS_B = ["Cinder", "Dune", "Frost", "Kite", "Vale"]


def build_sample_match() -> MatchData:
    rounds, kills, positions, grenades = [], [], [], []
    score_a = score_b = 0
    for r in range(1, 25):
        a_side = "T" if r <= 12 else "CT"
        b_side = "CT" if a_side == "T" else "T"
        winner = TEAM_A if r in {1, 3, 4, 6, 9, 11, 13, 14, 16, 19, 22, 24} else TEAM_B
        winning_side = a_side if winner == TEAM_A else b_side
        score_a += winner == TEAM_A
        score_b += winner == TEAM_B
        rounds.append({"round": r, "winner": winner, "winning_side": winning_side,
                       "team_a_score": score_a, "team_b_score": score_b,
                       "reason": "bomb_defused" if r % 4 == 0 else "elimination"})

        first_team = TEAM_A if r % 3 else TEAM_B
        second_team = TEAM_B if first_team == TEAM_A else TEAM_A
        first_players = PLAYERS_A if first_team == TEAM_A else PLAYERS_B
        second_players = PLAYERS_B if second_team == TEAM_B else PLAYERS_A
        area = "Mid" if r % 4 in {1, 2} else "A" if r % 4 == 3 else "B"
        x, y = {"Mid": (50, 51), "A": (78, 72), "B": (22, 28)}[area]
        first_side = a_side if first_team == TEAM_A else b_side
        kills.append({"round": r, "attacker": first_players[r % 5], "victim": second_players[(r + 2) % 5],
                      "attacker_team": first_team, "victim_team": second_team, "attacker_side": first_side,
                      "x": x + (r % 3 - 1) * 3, "y": y + (r % 5 - 2) * 2,
                      "seconds": 20 + (r * 7) % 42, "is_first_kill": True})
        if r in {5, 12, 18, 23}:
            clutch_team = TEAM_A if r in {12, 23} else TEAM_B
            players = PLAYERS_A if clutch_team == TEAM_A else PLAYERS_B
            kills.append({"round": r, "attacker": players[(r + 1) % 5], "victim": "last_opponent",
                          "attacker_team": clutch_team, "victim_team": TEAM_B if clutch_team == TEAM_A else TEAM_A,
                          "attacker_side": a_side if clutch_team == TEAM_A else b_side,
                          "x": 66, "y": 38, "seconds": 83, "is_first_kill": False})

        for team, players, side, anchor in ((TEAM_A, PLAYERS_A, a_side, (49, 50)), (TEAM_B, PLAYERS_B, b_side, (52, 50))):
            for idx, player in enumerate(players):
                for point, seconds in enumerate((20, 50, 80)):
                    angle = (idx * 1.7 + r * 0.31 + point) % (2 * math.pi)
                    radius = 11 + 4 * point + (idx % 2) * 3
                    px, py = anchor[0] + math.cos(angle) * radius, anchor[1] + math.sin(angle) * radius
                    area_name = "Mid" if 37 < px < 63 else "A" if px >= 63 else "B"
                    positions.append({"round": r, "player": player, "team": team, "side": side,
                                      "seconds": seconds, "x": px, "y": py, "area": area_name})
                if idx < 3:
                    grenades.append({"round": r, "thrower": player, "team": team,
                                     "grenade_type": ("Smoke", "Flash", "Molotov")[idx], "seconds": 18 + idx * 12,
                                     "x": anchor[0] + idx * 5, "y": anchor[1] - idx * 4})
    return MatchData("Astra vs Northstar · Synthetic walkthrough", "Mirage-style tactical plane", TEAM_A, TEAM_B,
                     "synthetic", pd.DataFrame(rounds), pd.DataFrame(kills), pd.DataFrame(positions), pd.DataFrame(grenades))
