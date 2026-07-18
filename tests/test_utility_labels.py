from src.sample_match import build_sample_match
from src.utility_labels import smoke_landing_annotations


def _allow_fractional_landing_coordinates(data) -> None:
    data.grenades["x"] = data.grenades["x"].astype("float64")
    data.grenades["y"] = data.grenades["y"].astype("float64")


def test_smoke_annotation_uses_nearest_observed_area() -> None:
    data = build_sample_match()
    _allow_fractional_landing_coordinates(data)
    smoke_index = data.grenades.index[0]
    data.grenades.loc[smoke_index, "grenade_type"] = "smoke"
    target = data.positions.loc[data.positions["area"] == "Mid"].iloc[0]
    data.grenades.loc[smoke_index, ["x", "y"]] = [target["x"], target["y"]]

    annotations = smoke_landing_annotations(data)
    row = annotations.loc[annotations["grenade_id"] == smoke_index].iloc[0]

    assert row["area"] == "Mid"
    assert row["area_distance"] == 0
    assert row["display_name"] == "烟雾弹"
    assert not bool(row["is_named"])


def test_named_mirage_area_keeps_landing_provenance() -> None:
    data = build_sample_match()
    _allow_fractional_landing_coordinates(data)
    smoke_index = data.grenades.index[0]
    data.grenades.loc[smoke_index, "grenade_type"] = "smoke"
    reference_index = data.positions.index[0]
    data.positions.loc[reference_index, "area"] = "Connector"
    data.grenades.loc[smoke_index, ["x", "y"]] = data.positions.loc[
        reference_index, ["x", "y"]
    ].to_numpy()

    annotations = smoke_landing_annotations(data)
    row = annotations.loc[annotations["grenade_id"] == smoke_index].iloc[0]

    assert row["area"] == "Connector"
    assert row["area_label"] == "拱门"
    assert row["display_name"] == "拱门烟"
    assert row["community_name"] == "拱门烟"
    assert row["label_source"] == "明确目标区域"
    assert bool(row["is_named"])


def test_landing_area_does_not_claim_a_community_smoke_name() -> None:
    data = build_sample_match()
    _allow_fractional_landing_coordinates(data)
    smoke_index = data.grenades.index[0]
    data.grenades.loc[smoke_index, "grenade_type"] = "smoke"
    reference = data.positions.iloc[0].copy()
    data.positions.loc[len(data.positions)] = [
        reference["round"],
        "catwalk-reference",
        reference["team"],
        reference["side"],
        reference["seconds"],
        777.0,
        888.0,
        "Catwalk",
    ]
    data.grenades.loc[smoke_index, ["x", "y"]] = [777.0, 888.0]

    row = smoke_landing_annotations(data).iloc[0]

    assert row["area_label"] == "B 小"
    assert row["display_name"] == "烟雾弹"
    assert row["community_name"] == ""
    assert row["label_source"] == "普通烟雾"


def test_far_smoke_is_not_given_a_named_area() -> None:
    data = build_sample_match()
    data.grenades.loc[:, "grenade_type"] = "flash"
    smoke_index = data.grenades.index[0]
    data.grenades.loc[smoke_index, "grenade_type"] = "smoke"
    data.grenades.loc[smoke_index, ["x", "y"]] = [9999.0, 9999.0]

    annotations = smoke_landing_annotations(data, max_area_distance=8.0)
    row = annotations.iloc[0]

    assert row["area"] == ""
    assert row["display_name"] == "烟雾弹"
    assert not bool(row["is_named"])
