"""Transform CS2 world coordinates onto audited 1024px radar assets."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ASSET_DIR = Path(__file__).resolve().parents[1] / "data" / "map_assets"


def load_map_metadata(map_name: str) -> dict[str, float]:
    metadata_path = ASSET_DIR / "map-data.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if map_name not in metadata:
        raise KeyError(f"没有找到 {map_name} 的雷达坐标参数")
    return metadata[map_name]


def radar_image_path(map_name: str) -> Path:
    path = ASSET_DIR / f"{map_name}.png"
    if not path.is_file():
        raise FileNotFoundError(f"没有找到雷达底图：{path}")
    return path


def game_to_radar(map_name: str, x: float, y: float) -> tuple[float, float]:
    metadata = load_map_metadata(map_name)
    return (
        (float(x) - float(metadata["pos_x"])) / float(metadata["scale"]),
        (float(metadata["pos_y"]) - float(y)) / float(metadata["scale"]),
    )


def project_frame(frame: pd.DataFrame, map_name: str, *, x: str = "x", y: str = "y") -> pd.DataFrame:
    """Add radar_x/radar_y and discard coordinates outside the radar canvas."""
    if frame.empty:
        return frame.assign(radar_x=pd.Series(dtype=float), radar_y=pd.Series(dtype=float))
    metadata = load_map_metadata(map_name)
    projected = frame.dropna(subset=[x, y]).copy()
    projected["radar_x"] = (projected[x].astype(float) - float(metadata["pos_x"])) / float(metadata["scale"])
    projected["radar_y"] = (float(metadata["pos_y"]) - projected[y].astype(float)) / float(metadata["scale"])
    return projected.loc[projected["radar_x"].between(0, 1024) & projected["radar_y"].between(0, 1024)]
