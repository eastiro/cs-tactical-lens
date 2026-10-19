"""Evidence-backed smoke labels derived from landing regions and trajectories.

The demo tells us where a smoke landed, but not the community name or the
thrower's tactical purpose.  This module therefore exposes an auditable
``起点 → 落点`` description.  A future verified signature table may add a
community name, but a landing region alone must never be promoted to one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import MatchData
from .tactics import AREA_LABEL

ANNOTATION_COLUMNS = [
    "grenade_id",
    "round",
    "thrower",
    "team",
    "seconds",
    "land_seconds",
    "x",
    "y",
    "area",
    "area_label",
    "throw_area",
    "throw_area_label",
    "display_name",
    "area_distance",
    "throw_area_distance",
    "community_name",
    "label_source",
    "is_named",
]

# These are the small set of target names that are clear enough to expose as
# community callouts from the current evidence.  Catwalk/Bombsite/Stairs are
# intentionally absent: a smoke there can be a standard smoke, a cross smoke,
# or a one-off transition, and the landing area alone cannot distinguish them.
MIRAGE_OBVIOUS_TARGET_NAMES = {
    "CTSpawn": "警家烟",
    "Connector": "拱门烟",
    "Jungle": "Jungle 烟",
    "Shop": "超市烟",
    "SnipersNest": "VIP 烟",
}


def smoke_landing_annotations(
    data: MatchData,
    *,
    max_area_distance: float = 32.0,
) -> pd.DataFrame:
    """Attach an auditable nearest-area label to every smoke landing.

    The reference cloud comes from player positions in the same parsed match,
    whose ``area`` values originate from the demo parser's navigation data.
    Labels beyond ``max_area_distance`` are left unnamed instead of guessed.
    """
    if data.grenades.empty or data.positions.empty:
        return pd.DataFrame(columns=ANNOTATION_COLUMNS)

    grenade_types = (
        data.grenades["grenade_type"]
        .astype(str)
        .str.lower()
        .str.replace("_", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    smokes = data.grenades.loc[
        grenade_types.isin({"smoke", "smokegrenade"})
    ].copy()
    references = (
        data.positions.dropna(subset=["x", "y", "area"])
        .drop_duplicates(["x", "y", "area"])
        .copy()
    )
    if smokes.empty or references.empty:
        return pd.DataFrame(columns=ANNOTATION_COLUMNS)

    reference_xy = references[["x", "y"]].to_numpy(dtype=float)
    reference_areas = references["area"].astype(str).to_numpy()

    def nearest_area(point: object) -> tuple[str, str, float]:
        if point is None:
            return "", "", float("inf")
        coordinates = np.asarray(point, dtype=float)
        if coordinates.shape != (2,) or not np.isfinite(coordinates).all():
            return "", "", float("inf")
        distances = np.linalg.norm(reference_xy - coordinates, axis=1)
        nearest_index = int(distances.argmin())
        area = str(reference_areas[nearest_index])
        distance = float(distances[nearest_index])
        return area, AREA_LABEL.get(area, area), distance

    records: list[dict[str, object]] = []

    for grenade_id, smoke in smokes.iterrows():
        area, area_label, distance = nearest_area(
            [smoke.get("x"), smoke.get("y")]
        )
        throw_area, throw_area_label, throw_distance = nearest_area(
            [smoke.get("throw_x"), smoke.get("throw_y")]
        )
        community_name = (
            MIRAGE_OBVIOUS_TARGET_NAMES.get(area, "")
            if distance <= float(max_area_distance)
            else ""
        )
        is_named = bool(community_name)
        land_value = smoke.get("land_seconds", smoke["seconds"])
        land_seconds = (
            float(smoke["seconds"])
            if pd.isna(land_value)
            else float(land_value)
        )
        records.append(
            {
                "grenade_id": int(grenade_id),
                "round": int(smoke["round"]),
                "thrower": str(smoke["thrower"]),
                "team": str(smoke["team"]),
                "seconds": float(smoke["seconds"]),
                "land_seconds": land_seconds,
                "x": float(smoke["x"]),
                "y": float(smoke["y"]),
                "area": area if distance <= float(max_area_distance) else "",
                "area_label": area_label if distance <= float(max_area_distance) else "",
                "throw_area": (
                    throw_area if throw_distance <= float(max_area_distance) else ""
                ),
                "throw_area_label": (
                    throw_area_label
                    if throw_distance <= float(max_area_distance)
                    else ""
                ),
                "display_name": community_name or "烟雾弹",
                "area_distance": distance,
                "throw_area_distance": throw_distance,
                "community_name": community_name,
                "label_source": "明确目标区域" if is_named else "普通烟雾",
                "is_named": bool(is_named),
            }
        )

    return pd.DataFrame.from_records(records, columns=ANNOTATION_COLUMNS)
