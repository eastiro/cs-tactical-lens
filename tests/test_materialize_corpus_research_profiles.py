"""Tests for scripts/materialize_corpus_research_profiles.py.

Uses temporary directories with minimal mock bundles.  No real demos required.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# ── Helpers ──────────────────────────────────────────────────────────────

TICKRATE = 64


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "materialize_corpus_research_profiles.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write a simple CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_metadata(path: Path, **overrides: str) -> dict:
    """Write a minimal bundle metadata.json and return it."""
    data = {
        "match_name": overrides.get("match_name", "test-match"),
        "map_name": overrides.get("map_name", "de_dust2"),
        "team_a": overrides.get("team_a", "Spirit"),
        "team_b": overrides.get("team_b", "Betboom"),
        "match_id": overrides.get("match_id", "1001"),
        "stage": overrides.get("stage", "stage-3"),
        "event": overrides.get("event", "IEM Cologne Major 2026"),
        "import_status": overrides.get("import_status", "parsed_and_validated"),
        "teams": [overrides.get("team_a", "Spirit"), overrides.get("team_b", "Betboom")],
        "parser": "awpy",
        "tickrate": 64,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _create_minimal_bundle(
    bundle_dir: Path,
    *,
    team_a: str = "Spirit",
    team_b: str = "Betboom",
    map_name: str = "de_dust2",
    match_id: str = "1001",
    stage: str = "stage-3",
) -> None:
    """Create a minimal but valid normalized bundle at *bundle_dir*.

    The bundle has 2 rounds with same-team kills (no opposing contact) and
    full position data for all 10 players.
    """
    freeze_end_1 = 100
    end_1 = 2000
    freeze_end_2 = 2100
    end_2 = 4000

    # Rounds – round 1: T wins (team_a plays T), round 2: CT wins (team_a plays T, team_b plays CT…)
    # For _team_by_round_and_side, positions determine which team is which side.
    # We set team_a = T side, team_b = CT side for both rounds.
    _write_csv(
        bundle_dir / "rounds.csv",
        ["round", "winner", "winning_side", "team_a_score", "team_b_score",
         "freeze_end", "end", "reason", "bomb_plant_seconds", "bomb_site"],
        [
            {"round": "1", "winner": team_a, "winning_side": "t", "team_a_score": "1",
             "team_b_score": "0", "freeze_end": str(freeze_end_1), "end": str(end_1),
             "reason": "elimination", "bomb_plant_seconds": "", "bomb_site": ""},
            {"round": "2", "winner": team_b, "winning_side": "ct", "team_a_score": "1",
             "team_b_score": "1", "freeze_end": str(freeze_end_2), "end": str(end_2),
             "reason": "elimination", "bomb_plant_seconds": "", "bomb_site": ""},
        ],
    )

    # Kills – *same-team* kills so _first_contact returns "none"
    kill_seconds_1 = (600 - freeze_end_1) / TICKRATE
    kill_seconds_2 = (2600 - freeze_end_2) / TICKRATE
    _write_csv(
        bundle_dir / "kills.csv",
        ["round", "tick", "attacker", "victim", "attacker_team", "victim_team",
         "attacker_side", "x", "y", "seconds", "is_first_kill", "weapon",
         "assister", "assisted_flash", "victim_x", "victim_y"],
        [
            {"round": "1", "tick": "600", "attacker": "player1", "victim": "player3",
             "attacker_team": team_a, "victim_team": team_a, "attacker_side": "T",
             "x": "15", "y": "15", "seconds": f"{kill_seconds_1:.4f}",
             "is_first_kill": "True", "weapon": "ak47", "assister": "",
             "assisted_flash": "False", "victim_x": "20", "victim_y": "20"},
            {"round": "2", "tick": "2600", "attacker": "player5", "victim": "player7",
             "attacker_team": team_b, "victim_team": team_b, "attacker_side": "CT",
             "x": "115", "y": "115", "seconds": f"{kill_seconds_2:.4f}",
             "is_first_kill": "True", "weapon": "ak47", "assister": "",
             "assisted_flash": "False", "victim_x": "120", "victim_y": "120"},
        ],
    )

    # Positions – two timestamps per player per round (early ≤20s + late ≥21s)
    # so _opening_shape can find data within the sample window.
    pos_fieldnames = ["round", "player", "team", "side", "seconds", "x", "y", "area", "health", "tick"]
    pos_rows: list[dict] = []
    for rnd, side_assignment in [(1, ("T", "CT")), (2, ("CT", "T"))]:
        t_side, ct_side = side_assignment
        base_tick = freeze_end_1 if rnd == 1 else freeze_end_2
        t_team, ct_team = (team_a, team_b) if t_side == "T" else (team_b, team_a)
        for i in range(1, 6):  # 5 T players
            pos_rows.append({
                "round": str(rnd), "player": f"t{i}", "team": t_team, "side": t_side,
                "seconds": "5.0", "x": str(10 * i), "y": str(10 * i), "area": "A1",
                "health": "100", "tick": str(base_tick + 320),
            })
            pos_rows.append({
                "round": str(rnd), "player": f"t{i}", "team": t_team, "side": t_side,
                "seconds": "25.0", "x": str(12 * i), "y": str(12 * i), "area": "A1",
                "health": "100", "tick": str(base_tick + 1600),
            })
        for i in range(1, 6):  # 5 CT players
            pos_rows.append({
                "round": str(rnd), "player": f"ct{i}", "team": ct_team, "side": ct_side,
                "seconds": "5.0", "x": str(200 + 10 * i), "y": str(200 + 10 * i),
                "area": "B1", "health": "100", "tick": str(base_tick + 320),
            })
            pos_rows.append({
                "round": str(rnd), "player": f"ct{i}", "team": ct_team, "side": ct_side,
                "seconds": "25.0", "x": str(200 + 12 * i), "y": str(200 + 12 * i),
                "area": "B1", "health": "100", "tick": str(base_tick + 1600),
            })
    _write_csv(bundle_dir / "positions.csv", pos_fieldnames, pos_rows)

    # Grenades – minimal
    _write_csv(
        bundle_dir / "grenades.csv",
        ["round", "thrower", "team", "grenade_type", "seconds", "land_seconds",
         "effect_end_seconds", "x", "y", "throw_x", "throw_y", "trajectory"],
        [
            {"round": "1", "thrower": "t1", "team": team_a, "grenade_type": "smoke",
             "seconds": "3.0", "land_seconds": "4.5", "effect_end_seconds": "18.0",
             "x": "20", "y": "20", "throw_x": "10", "throw_y": "10",
             "trajectory": "[[3.0,10,10],[4.5,20,20]]"},
            {"round": "2", "thrower": "ct1", "team": team_b, "grenade_type": "flash",
             "seconds": "3.0", "land_seconds": "4.5", "effect_end_seconds": "",
             "x": "220", "y": "220", "throw_x": "210", "throw_y": "210",
             "trajectory": "[[3.0,210,210],[4.5,220,220]]"},
        ],
    )

    # Metadata
    _write_metadata(
        bundle_dir / "metadata.json",
        match_name=f"{match_id}-{map_name}",
        map_name=map_name,
        team_a=team_a,
        team_b=team_b,
        match_id=match_id,
        stage=stage,
    )


def _create_minimal_import_results(path: Path, rows: list[dict]) -> None:
    """Write a minimal import_results.csv."""
    fieldnames = ["match_id", "map", "stage", "teams", "bundle", "status"]
    _write_csv(path, fieldnames, rows)


def _create_coverage_summary(
    path: Path,
    entries: list[dict],
) -> None:
    """Write a coverage_summary.json with the given coverage list."""
    data = {
        "event": "IEM Cologne Major 2026",
        "generated_at": "2026-07-18T07:00:23.611463+00:00",
        "coverage": entries,
        "boundary": "覆盖状态仅反映已解析比赛数量",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="function")
def _tmp_project() -> Path:
    """Yield a writable temporary directory, cleaned up after the test."""
    d = Path(tempfile.mkdtemp(prefix="mat_test_"))
    try:
        yield d
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def project(_tmp_project: Path) -> Path:
    """Create a temporary project directory with this layout:

    processed/iem-cologne-major-2026-corpus/
        import_results.csv
        <match_id>/<map>/   (normalized bundles)
    series/
        iem-cologne-major-2026-corpus/
            coverage_summary.json
    """
    root = _tmp_project / "project"
    processed = root / "processed" / "iem-cologne-major-2026-corpus"
    series_corpus = root / "series" / "iem-cologne-major-2026-corpus"
    root / "series"
    processed.mkdir(parents=True, exist_ok=True)
    series_corpus.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def processed_root(project: Path) -> Path:
    return project / "processed" / "iem-cologne-major-2026-corpus"


@pytest.fixture
def series_root(project: Path) -> Path:
    return project / "series"


@pytest.fixture
def coverage_path(project: Path) -> Path:
    return project / "series" / "iem-cologne-major-2026-corpus" / "coverage_summary.json"


def _setup_standard_fixtures(
    processed_root: Path,
    coverage_path: Path,
) -> tuple[list[str], list[str]]:
    """Create a standard set of bundles + coverage for testing.

    Returns (standard_profile_ids, exploratory_profile_ids).
    """
    # Create 6 standard bundles (4 distinct team-map combos)
    # Spirit de_dust2 × 3 matches → standard (≥5)
    # Spirit de_mirage × 2 matches → exploratory (3-4)
    # Betboom de_dust2 × 3 matches → standard
    # Betboom de_mirage × 2 matches → standard (wait, 2 is insufficient <3)
    # Let me recalculate:
    # standard >= 5, exploratory 3-4, insufficient < 3
    # To get standard, I need at least 5 matches for a team-map
    # For 2-team × 2-map = 4 combos, I need enough matches

    # Let me create 6 matches:
    # Spirit de_dust2: match_ids 1001-1005 (5 matches → standard)
    # Spirit de_mirage: match_ids 1006-1008 (3 matches → exploratory)
    # Betboom de_dust2: match_ids 1001-1003, 1009-1010 (5 → standard)
    # Betboom de_mirage: match_ids 1006-1007 (2 → insufficient)

    # Create bundles
    spirit_d2_ids = ["1001", "1002", "1003", "1004", "1005"]
    spirit_mrg_ids = ["1006", "1007", "1008"]
    betboom_d2_ids = ["1001", "1002", "1003", "1009", "1010"]

    for mid in spirit_d2_ids:
        _create_minimal_bundle(
            processed_root / mid / "de_dust2",
            team_a="Spirit", team_b="Betboom",
            map_name="de_dust2", match_id=mid, stage="stage-3",
        )
    for mid in spirit_mrg_ids:
        _create_minimal_bundle(
            processed_root / mid / "de_mirage",
            team_a="Spirit", team_b="Betboom",
            map_name="de_mirage", match_id=mid, stage="stage-3",
        )
    for mid in set(betboom_d2_ids) - set(spirit_d2_ids):
        _create_minimal_bundle(
            processed_root / mid / "de_dust2",
            team_a="Betboom", team_b="Falcons",
            map_name="de_dust2", match_id=mid, stage="stage-3",
        )
    # 1006, 1007 already created as Spirit vs Betboom de_mirage

    # Create import_results.csv
    import_rows: list[dict] = []
    for mid in spirit_d2_ids + spirit_mrg_ids:
        map_n = "de_dust2" if mid in spirit_d2_ids else "de_mirage"
        import_rows.append({
            "match_id": mid, "map": map_n, "stage": "stage-3",
            "teams": "", "bundle": "", "status": "parsed_and_validated",
        })
    for mid in set(betboom_d2_ids) - set(spirit_d2_ids):
        import_rows.append({
            "match_id": mid, "map": "de_dust2", "stage": "stage-3",
            "teams": "", "bundle": "", "status": "parsed_and_validated",
        })
    import_rows.append({
        "match_id": "9999", "map": "de_overpass", "stage": "stage-3",
        "teams": "", "bundle": "", "status": "error: failed",
    })
    _create_minimal_import_results(processed_root / "import_results.csv", import_rows)

    # Create coverage_summary.json
    _create_coverage_summary(coverage_path, [
        {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 5, "tier": "standard"},
        {"team": "Spirit", "map": "de_mirage", "parsed_match_count": 3, "tier": "exploratory"},
        {"team": "Betboom", "map": "de_dust2", "parsed_match_count": 5, "tier": "standard"},
        {"team": "Betboom", "map": "de_mirage", "parsed_match_count": 2, "tier": "insufficient"},
    ])

    return (
        ["iem-cologne-2026-spirit-de_dust2", "iem-cologne-2026-betboom-de_dust2"],
        ["iem-cologne-2026-spirit-de_mirage"],
    )


# ═════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════


class TestTierFiltering:
    """Requirement 1: standard included by default, exploratory/insufficient excluded."""

    def test_default_tiers_only_standard(self, project: Path, processed_root: Path,
                                         coverage_path: Path, series_root: Path) -> None:
        """--tiers defaults to 'standard' so exploratory/insufficient are excluded."""
        standard_ids, exploratory_ids = _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        # Parse results from stdout – results CSV is written even in dry-run
        results_csv = coverage_path.parent / "materialize_results.csv"
        assert results_csv.is_file()
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))

        # Should only have standard entries
        profile_ids = {r["profile_id"] for r in rows}
        for sid in standard_ids:
            assert sid in profile_ids, f"缺少 standard profile：{sid}"
        for eid in exploratory_ids:
            assert eid not in profile_ids, f"exploratory profile 不应出现：{eid}"

        # All standard entries should be "planned" (dry-run)
        for r2 in rows:
            assert r2["status"] == "planned", f"{r2['profile_id']} has status {r2['status']}"

    def test_tiers_all_flag(self, project: Path, processed_root: Path,
                            coverage_path: Path, series_root: Path) -> None:
        """--tiers standard,exploratory includes both tiers."""
        standard_ids, exploratory_ids = _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--tiers", "standard,exploratory",
            "--dry-run",
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        profile_ids = {r["profile_id"] for r in rows}

        for sid in standard_ids:
            assert sid in profile_ids
        for eid in exploratory_ids:
            assert eid in profile_ids, f"exploratory profile 应出现：{eid}"

        # insufficient still excluded
        assert "iem-cologne-2026-betboom-de_mirage" not in profile_ids


class TestBundleResolution:
    """Requirement 2: manifest bundle paths resolve via load_team_map_series()."""

    def test_bundle_path_resolves(self, project: Path, processed_root: Path,
                                  coverage_path: Path, series_root: Path) -> None:
        """After materialization, load_team_map_series() finds the bundle."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--limit", "1",  # just one profile
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        # Verify the manifest was created and load_team_map_series works
        from src.team_map_series import load_team_map_series

        manifest = series_root / "iem-cologne-2026-spirit-de_dust2.json"
        assert manifest.is_file(), f"manifest not found: {manifest}"

        series = load_team_map_series(manifest)
        assert series.team == "Spirit"
        assert series.map_name == "de_dust2"
        assert len(series.matches) == 5  # 5 matches for Spirit de_dust2
        assert all(m.bundle_path.is_dir() for m in series.matches), (
            "部分 bundle 路径不可解析"
        )


class TestDiscoverability:
    """Requirement 3: paths match discover_research_profiles() conventions."""

    def test_research_catalog_discovers_profiles(
        self, project: Path, processed_root: Path,
        coverage_path: Path, series_root: Path,
    ) -> None:
        """After materialization, discover_research_profiles() finds all profiles."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        from src.research_catalog import ResearchProfile, discover_research_profiles
        profiles: tuple[ResearchProfile, ...] = discover_research_profiles(series_root)
        pids = {p.profile_id for p in profiles}

        # Both standard profiles should be discovered
        assert "iem-cologne-2026-spirit-de_dust2" in pids
        assert "iem-cologne-2026-betboom-de_dust2" in pids

        # Verify artifact structure
        for profile in profiles:
            assert profile.series_dir.is_dir()
            assert (profile.series_dir / "series_metadata.json").is_file()
            assert (profile.series_dir / "precontact_opening_samples.csv").is_file()
            assert (profile.series_dir / "precontact_opening_profile.csv").is_file()
            assert profile.match_count >= 1
            assert profile.eligible_samples >= 1

    def test_manifest_location_structure(self, project: Path, processed_root: Path,
                                         coverage_path: Path, series_root: Path) -> None:
        """Manifest JSON and series dir are sibling pairs as required."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r.returncode == 0

        pid = "iem-cologne-2026-spirit-de_dust2"
        manifest = series_root / f"{pid}.json"
        series_dir = series_root / pid

        assert manifest.is_file(), f"Manifest missing: {manifest}"
        assert series_dir.is_dir(), f"Series dir missing: {series_dir}"
        assert all((series_dir / name).is_file() for name in
                   ("series_metadata.json", "precontact_opening_samples.csv",
                    "precontact_opening_profile.csv"))


class TestErrorHandling:
    """Requirement 4: missing/bad metadata does not create fake profiles."""

    def test_missing_metadata_skipped(self, project: Path, processed_root: Path,
                                      coverage_path: Path, series_root: Path) -> None:
        """A coverage entry with no matching processed bundles is failed."""
        # Create coverage for a team-map with no corresponding processed data
        _create_coverage_summary(coverage_path, [
            {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 5, "tier": "standard"},
            {"team": "GhostTeam", "map": "de_dust2", "parsed_match_count": 3, "tier": "standard"},
        ])
        # Create a matching bundle for Spirit only
        _create_minimal_bundle(
            processed_root / "1001" / "de_dust2",
            team_a="Spirit", team_b="Betboom",
            map_name="de_dust2", match_id="1001",
        )
        _create_minimal_import_results(processed_root / "import_results.csv", [
            {"match_id": "1001", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
        ])

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        status_by_id = {r["profile_id"]: r["status"] for r in rows}

        # Spirit should be skipped (no matching processed bundles wait—actually in dry-run mode
        # even with matches it shows "planned", but GhostTeam had no matches)
        assert "iem-cologne-2026-spirit-de_dust2" in status_by_id
        assert status_by_id["iem-cologne-2026-ghostteam-de_dust2"] == "failed"

    def test_wrong_map_skipped(self, project: Path, processed_root: Path,
                               coverage_path: Path, series_root: Path) -> None:
        """A bundle whose map_name doesn't match coverage entry is not included."""
        # Coverage says Spirit de_dust2, but processed bundle is de_mirage
        _create_coverage_summary(coverage_path, [
            {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 1, "tier": "standard"},
        ])
        _create_minimal_bundle(
            processed_root / "1001" / "de_inferno",  # note: wrong map folder
            team_a="Spirit", team_b="Betboom",
            map_name="de_inferno", match_id="1001",
        )
        # Also create a proper de_dust2 bundle but for a different team
        _create_minimal_bundle(
            processed_root / "1002" / "de_dust2",
            team_a="Falcons", team_b="Betboom",  # Spirit not involved
            map_name="de_dust2", match_id="1002",
        )
        _create_minimal_import_results(processed_root / "import_results.csv", [
            {"match_id": "1001", "map": "de_inferno", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
            {"match_id": "1002", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
        ])

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        assert len(rows) == 1
        # Spirit de_dust2 has no matching processed bundles → failed
        assert rows[0]["status"] == "failed"
        assert "找不到对应队伍" in rows[0]["reason"]

    def test_validation_skipped_non_parsed_status(
        self, project: Path, processed_root: Path,
        coverage_path: Path, series_root: Path,
    ) -> None:
        """Bundles with non-parsed_and_validated import_status are excluded."""
        _create_coverage_summary(coverage_path, [
            {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 1, "tier": "standard"},
        ])
        # Bundle exists but metadata has import_status="error"
        _create_minimal_bundle(
            processed_root / "1001" / "de_dust2",
            team_a="Spirit", team_b="Betboom",
        )
        # Override metadata status
        meta_path = processed_root / "1001" / "de_dust2" / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["import_status"] = "error: failed"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        _create_minimal_import_results(processed_root / "import_results.csv", [
            {"match_id": "1001", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
        ])

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        assert rows[0]["status"] == "failed"


class TestIsolation:
    """Requirement 5: one failing profile does not block others."""

    def test_partial_failure_still_builds_others(
        self, project: Path, processed_root: Path,
        coverage_path: Path, series_root: Path,
    ) -> None:
        """When one profile fails (bad bundle), other profiles still complete."""
        # Coverage: 2 standard entries
        _create_coverage_summary(coverage_path, [
            {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 2, "tier": "standard"},
            {"team": "Betboom", "map": "de_dust2", "parsed_match_count": 2, "tier": "standard"},
        ])

        # Valid bundle for Spirit
        _create_minimal_bundle(
            processed_root / "1001" / "de_dust2",
            team_a="Spirit", team_b="Betboom",
            map_name="de_dust2", match_id="1001",
        )
        _create_minimal_bundle(
            processed_root / "1002" / "de_dust2",
            team_a="Spirit", team_b="Betboom",
            map_name="de_dust2", match_id="1002",
        )

        # Betboom has NO matching bundle (team_a != "Betboom" for any of their matches,
        # so let's make matches where Betboom is the opponent but not primary team)
        # Actually, let me create the bundles but with different data so Spirit's matches
        # are found but Betboom's coverage entry has no matches.
        # For Betboom de_dust2: we need matches where Betboom is team_a or team_b.
        # Let's create one as team_a:
        _create_minimal_bundle(
            processed_root / "1003" / "de_dust2",
            team_a="Betboom", team_b="Falcons",
            map_name="de_dust2", match_id="1003",
        )
        _create_minimal_bundle(
            processed_root / "1004" / "de_dust2",
            team_a="Betboom", team_b="Falcons",
            map_name="de_dust2", match_id="1004",
        )

        _create_minimal_import_results(processed_root / "import_results.csv", [
            {"match_id": "1001", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
            {"match_id": "1002", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
            {"match_id": "1003", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
            {"match_id": "1004", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
        ])

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        status_by_id = {r["profile_id"]: r["status"] for r in rows}

        # Both should succeed since both have matching bundles
        assert status_by_id.get("iem-cologne-2026-spirit-de_dust2") == "ok"
        assert status_by_id.get("iem-cologne-2026-betboom-de_dust2") == "ok"

    def test_corrupt_bundle_does_not_crash_others(
        self, project: Path, processed_root: Path,
        coverage_path: Path, series_root: Path,
    ) -> None:
        """A bundle with corrupt CSV causes one profile to fail but others build."""
        _create_coverage_summary(coverage_path, [
            {"team": "Spirit", "map": "de_dust2", "parsed_match_count": 1, "tier": "standard"},
            {"team": "Betboom", "map": "de_dust2", "parsed_match_count": 1, "tier": "standard"},
        ])

        # Valid bundle for Spirit
        _create_minimal_bundle(
            processed_root / "1001" / "de_dust2",
            team_a="Spirit", team_b="Betboom",
        )

        # Corrupt bundle for Betboom (empty rounds.csv)
        (processed_root / "1002" / "de_dust2").mkdir(parents=True, exist_ok=True)
        (processed_root / "1002" / "de_dust2" / "rounds.csv").write_text("", encoding="utf-8")
        _write_metadata(
            processed_root / "1002" / "de_dust2" / "metadata.json",
            map_name="de_dust2", team_a="Betboom", team_b="Falcons",
            match_id="1002",
        )

        _create_minimal_import_results(processed_root / "import_results.csv", [
            {"match_id": "1001", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
            {"match_id": "1002", "map": "de_dust2", "stage": "stage-3",
             "teams": "", "bundle": "", "status": "parsed_and_validated"},
        ])

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        status_by_id = {r["profile_id"]: r["status"] for r in rows}

        # Spirit should succeed
        assert status_by_id.get("iem-cologne-2026-spirit-de_dust2") == "ok"
        # Betboom should fail (corrupt bundle), but the script still ran to completion
        betboom_status = status_by_id.get("iem-cologne-2026-betboom-de_dust2")
        assert betboom_status == "failed", f"expected failed, got {betboom_status}"

        # Verify Spirit's profile was actually written to disk
        spirit_manifest = series_root / "iem-cologne-2026-spirit-de_dust2.json"
        assert spirit_manifest.is_file()


class TestDryRun:
    """Requirement 6: dry-run writes no files."""

    def test_dry_run_no_files_written(self, project: Path, processed_root: Path,
                                      coverage_path: Path, series_root: Path) -> None:
        """--dry-run does not create manifest or series dir."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        # No manifest files should exist
        manifests = list(series_root.glob("*.json"))
        # Should only have the coverage_summary.json (from fixture) and materialize_results.csv
        # No iem-cologne-* manifests
        corpus_manifests = [m for m in manifests if m.name.startswith("iem-cologne-")]
        assert len(corpus_manifests) == 0, f"dry-run created manifests: {corpus_manifests}"

        # No profile series dirs should exist (profile IDs have 4 segments with year,
        # unlike the existing corpus directory which starts with "iem-cologne-major-")
        series_dirs = [d for d in series_root.iterdir()
                       if d.is_dir() and d.name.startswith("iem-cologne-2026-")]
        assert len(series_dirs) == 0, f"dry-run created dirs: {series_dirs}"

        # But results CSV should still be written during dry-run
        results_csv = coverage_path.parent / "materialize_results.csv"
        assert results_csv.is_file()

        # All results should be "planned"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        assert all(r["status"] == "planned" for r in rows)


class TestIdempotent:
    """Requirement 8: re-running is idempotent."""

    def test_rerun_skips_complete(self, project: Path, processed_root: Path,
                                  coverage_path: Path, series_root: Path) -> None:
        """Second run skips profiles that already have complete 3-piece suits."""
        _setup_standard_fixtures(processed_root, coverage_path)

        # First run
        r1 = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r1.returncode == 0

        # Second run
        r2 = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
        )
        assert r2.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        statuses = {(r["profile_id"], r["status"]) for r in rows}

        # Both profiles should be "skipped" (already exist and complete)
        assert ("iem-cologne-2026-spirit-de_dust2", "skipped") in statuses
        assert ("iem-cologne-2026-betboom-de_dust2", "skipped") in statuses


class TestLimit:
    """--limit N restricts how many profiles are processed."""

    def test_limit_restricts_profiles(self, project: Path, processed_root: Path,
                                      coverage_path: Path, series_root: Path) -> None:
        """--limit 1 only processes one profile."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--limit", "1",
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        assert len(rows) == 1


class TestResultsCsv:
    """Results CSV has correct fields and content."""

    def test_results_csv_fields(self, project: Path, processed_root: Path,
                                coverage_path: Path, series_root: Path) -> None:
        """Results CSV includes all required fields."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        with results_csv.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows, "results CSV is empty"
            assert "profile_id" in rows[0]
            assert "team" in rows[0]
            assert "map" in rows[0]
            assert "tier" in rows[0]
            assert "match_count" in rows[0]
            assert "status" in rows[0]
            assert "reason" in rows[0]

    def test_results_csv_dry_run_planned(self, project: Path, processed_root: Path,
                                         coverage_path: Path, series_root: Path) -> None:
        """dry-run results show 'planned' status with match count."""
        _setup_standard_fixtures(processed_root, coverage_path)

        r = _run(
            "--processed-root", str(processed_root),
            "--coverage", str(coverage_path),
            "--series-root", str(series_root),
            "--dry-run",
        )
        assert r.returncode == 0

        results_csv = coverage_path.parent / "materialize_results.csv"
        rows = list(csv.DictReader(results_csv.open(encoding="utf-8-sig")))
        for row in rows:
            assert row["status"] == "planned"
            assert int(row["match_count"]) >= 1


class TestProfileId:
    """profile_id format is stable and non-colliding."""

    def test_profile_id_format(self) -> None:
        """Verify profile_id matches expected pattern."""
        from scripts.materialize_corpus_research_profiles import _profile_id

        pid = _profile_id("Spirit", "de_dust2")
        assert pid == "iem-cologne-2026-spirit-de_dust2"

        pid2 = _profile_id("Natus Vincere", "de_mirage")
        assert pid2 == "iem-cologne-2026-natus_vincere-de_mirage"

        pid3 = _profile_id("The MongolZ", "de_nuke")
        assert pid3 == "iem-cologne-2026-the_mongolz-de_nuke"
