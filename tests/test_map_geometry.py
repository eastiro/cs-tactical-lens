import pandas as pd

from src.map_geometry import game_to_radar, project_frame, radar_image_path


def test_mirage_world_bounds_map_to_radar_corners():
    assert game_to_radar("de_mirage", -3230, 1713) == (0, 0)
    assert game_to_radar("de_mirage", 1890, -3407) == (1024, 1024)


def test_projection_drops_points_outside_radar():
    frame = pd.DataFrame({"x": [-3230, 99999], "y": [1713, 99999]})
    projected = project_frame(frame, "de_mirage")
    assert len(projected) == 1
    assert projected.iloc[0].radar_x == 0


def test_mirage_radar_asset_exists():
    assert radar_image_path("de_mirage").is_file()
