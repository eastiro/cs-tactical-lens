from __future__ import annotations

import json

from src.coverage_audit import coverage_rows, normalized_bundles, unassigned_bundles


def _profile(root, ident, team, *, matches=5):
    folder = root / ident
    folder.mkdir()
    (folder / "series_metadata.json").write_text(json.dumps({"match_count": matches, "eligible_precontact_samples": 30}), encoding="utf-8")
    (folder / "precontact_opening_samples.csv").write_text("round\n1\n", encoding="utf-8")
    (folder / "precontact_opening_profile.csv").write_text("formation\n2-1-2\n", encoding="utf-8")
    (root / f"{ident}.json").write_text(json.dumps({"team": team, "map": "de_mirage", "season": "test", "matches": []}), encoding="utf-8")


def test_coverage_requires_two_ready_teams_on_the_same_map(tmp_path):
    _profile(tmp_path, "falcons", "Team Falcons", matches=5)
    _profile(tmp_path, "spirit", "Team Spirit", matches=4)
    rows = coverage_rows(tmp_path)
    assert [row.pairable for row in rows] == [False, False]
    assert rows[1].matches_to_threshold == 1


def test_normalized_and_unassigned_bundles_are_read_only(tmp_path):
    processed = tmp_path / "processed"
    bundle = processed / "team" / "match" / "de_mirage"
    bundle.mkdir(parents=True)
    (bundle / "metadata.json").write_text(json.dumps({"map_name": "de_mirage"}), encoding="utf-8")
    assert normalized_bundles(processed) == (bundle.resolve(),)
    assert unassigned_bundles(tmp_path, processed) == (bundle.resolve(),)
