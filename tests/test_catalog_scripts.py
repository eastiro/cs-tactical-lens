"""Tests for scripts/catalog_match_archives.py and scripts/build_team_map_views.py.

These tests use a fake .zip archive and a bare .dem file to verify the catalog
and team-map-view pipeline without touching real demos or requiring 7-Zip.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers ────────────────────────────────────────────────────────────────


def _run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    """Run one of the scripts/ scripts with *args and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _fake_dem(name: str) -> bytes:
    """Return deterministic fake .dem content that differs by name."""
    return (name * 200).encode()[:1024]  # exactly 1024 bytes per demo


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    """Create a .zip at *path* containing *members* (name -> content)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """A temporary directory with a match .zip and one bare .dem."""
    d = tmp_path / "raw"
    d.mkdir()

    # BO3 zip with three map demos.  The zip filename determines match_slug,
    # and the member filenames determine map detection.  One member shares
    # its name with a bare .dem below so that duplicate detection triggers.
    _make_zip(d / "falcons-vs-furia-m1-mirage-bo3.zip", {
        "falcons-vs-furia-m1-mirage.dem": _fake_dem("mirage"),
        "furia-vs-falcons-m2-dust2.dem": _fake_dem("dust2"),
        "furia-vs-falcons-m3-inferno.dem": _fake_dem("inferno"),
    })

    # Bare .dem with the same filename AND size as the zipped mirage member →
    # should be flagged duplicate_member_candidate.
    (d / "falcons-vs-furia-m1-mirage.dem").write_bytes(_fake_dem("mirage"))

    # Another bare .dem with different size → NOT a duplicate.
    # Its filename still matches "mirage" so it counts toward target_map entries.
    diff = _fake_dem("mirage") + b"extra_bytes"
    (d / "falcons-vs-furia-m1-mirage-alt.dem").write_bytes(diff)

    return d


@pytest.fixture
def catalog_out(tmp_path: Path) -> Path:
    """Output directory for the catalog step."""
    return tmp_path / "catalog"


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    """A valid registry JSON with two matches."""
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({
        "matches": [
            {
                "match_slug": "falcons-vs-furia-m1-mirage",
                "teams": ["Team Falcons", "FURIA"],
                "event": "IEM Cologne Major 2026",
                "date": "2026-06-21",
            },
            {
                "match_slug": "falcons-vs-spirit-m2-mirage",
                "teams": ["Team Falcons", "Spirit"],
                "event": "IEM Cologne Major 2026",
                "date": "2026-06-20",
            },
        ],
    }), encoding="utf-8")
    return reg


# ═════════════════════════════════════════════════════════════════════════
#   catalog_match_archives.py
# ═════════════════════════════════════════════════════════════════════════


class TestCatalogMatchArchives:
    """Requirement 1 & 2 from the task."""

    def test_output_files_created(self, source_dir: Path, catalog_out: Path) -> None:
        """R1: all_maps.csv, maps/<map>/demos.csv, catalog_summary.json exist."""
        result = _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        assert (catalog_out / "all_maps.csv").is_file()
        assert (catalog_out / "maps" / "de_mirage" / "demos.csv").is_file()
        assert (catalog_out / "maps" / "de_dust2" / "demos.csv").is_file()
        assert (catalog_out / "maps" / "de_inferno" / "demos.csv").is_file()
        assert (catalog_out / "catalog_summary.json").is_file()

    def test_all_maps_csv_content(self, source_dir: Path, catalog_out: Path) -> None:
        """R1: all_maps.csv has 5 rows (2 from zip + 2 bare + 1 diff-size)."""
        _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        rows = list(csv.DictReader((catalog_out / "all_maps.csv").open(encoding="utf-8-sig")))
        # 3 from zip + 2 bare = 5
        assert len(rows) == 5, f"expected 5 rows, got {len(rows)}"

    def test_catalog_summary_content(self, source_dir: Path, catalog_out: Path) -> None:
        """R1: summary JSON has expected keys and counts."""
        _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        summary = json.loads((catalog_out / "catalog_summary.json").read_text(encoding="utf-8"))
        assert summary["team"] == "Team Falcons"
        assert summary["target_map"] == "de_mirage"
        assert summary["demo_entries"] == 5
        # 3 mirage entries (one from zip, two bare — same-size and diff-size)
        assert summary["target_map_entries"] == 3
        assert "maps" in summary
        assert "de_mirage" in summary["maps"]

    def test_duplicate_member_detected(self, source_dir: Path, catalog_out: Path) -> None:
        """R2: identically-named + same-size bare .dem is duplicate_member_candidate."""
        _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        rows = list(csv.DictReader((catalog_out / "all_maps.csv").open(encoding="utf-8-sig")))
        bare_demos = [r for r in rows if r["source_kind"] == "single_demo"]
        # The first bare demo (same name+size) should be duplicate
        same_size = [r for r in bare_demos if r["demo_size_bytes"] == "1024"]
        for row in same_size:
            assert row["catalog_status"] == "duplicate_member_candidate", (
                f"expected duplicate for {row['source_file']}"
            )

    def test_diff_size_not_duplicate(self, source_dir: Path, catalog_out: Path) -> None:
        """R2: different-sized bare .dem is NOT marked duplicate."""
        _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        rows = list(csv.DictReader((catalog_out / "all_maps.csv").open(encoding="utf-8-sig")))
        diff_size = [r for r in rows if "alt" in r.get("demo_member", "")]
        assert len(diff_size) == 1
        assert diff_size[0]["catalog_status"] != "duplicate_member_candidate"

    def test_inferno_map_csv(self, source_dir: Path, catalog_out: Path) -> None:
        """R1: maps/de_inferno/demos.csv was created."""
        _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        inf_csv = catalog_out / "maps" / "de_inferno" / "demos.csv"
        assert inf_csv.is_file()
        rows = list(csv.DictReader(inf_csv.open(encoding="utf-8-sig")))
        assert len(rows) == 1
        assert "inferno" in rows[0]["demo_member"]


# ═════════════════════════════════════════════════════════════════════════
#   build_team_map_views.py
# ═════════════════════════════════════════════════════════════════════════


class TestBuildTeamMapViews:
    """Requirements 3, 4 & 5 from the task."""

    @pytest.fixture(autouse=True)
    def _run_catalog_first(self, source_dir: Path, catalog_out: Path) -> None:
        """Ensure catalog is built before each team-map-view test."""
        result = _run_script(
            "catalog_match_archives.py",
            str(source_dir),
            "--team", "Team Falcons",
            "--target-map", "de_mirage",
            "--output", str(catalog_out),
        )
        assert result.returncode == 0
        self._catalog_out = catalog_out

    @pytest.fixture
    def team_view_out(self, tmp_path: Path) -> Path:
        return tmp_path / "team-views"

    @pytest.fixture
    def run_team_views(self, registry_file: Path, team_view_out: Path) -> Path:
        """Run build_team_map_views.py and return the output path."""
        result = _run_script(
            "build_team_map_views.py",
            str(self._catalog_out / "all_maps.csv"),
            "--registry", str(registry_file),
            "--primary-team", "Team Falcons",
            "--output", str(team_view_out),
            "--minimum-maps", "5",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        return team_view_out

    # ── R3 ──

    def test_mirage_appears_under_both_teams(
        self, run_team_views: Path, registry_file: Path,
    ) -> None:
        """R3: de_mirage appears under both Team Falcons and FURIA."""
        falcons = run_team_views / "team-falcons" / "maps" / "de_mirage" / "demos.csv"
        furia = run_team_views / "furia" / "maps" / "de_mirage" / "demos.csv"
        assert falcons.is_file(), f"missing {falcons}"
        assert furia.is_file(), f"missing {furia}"
        f_rows = list(csv.DictReader(falcons.open(encoding="utf-8-sig")))
        fu_rows = list(csv.DictReader(furia.open(encoding="utf-8-sig")))
        assert len(f_rows) >= 1
        assert all(r["team"] == "Team Falcons" for r in f_rows)
        assert len(fu_rows) >= 1
        assert all(r["team"] == "FURIA" for r in fu_rows)

    # ── R4 ──

    def test_dataset_scope_primary_team(
        self, run_team_views: Path,
    ) -> None:
        """R4: Team Falcons dir has primary_team_collection scope."""
        falcons_csv = run_team_views / "team-falcons" / "maps" / "de_mirage" / "demos.csv"
        rows = list(csv.DictReader(falcons_csv.open(encoding="utf-8-sig")))
        assert all(r["dataset_scope"] == "primary_team_collection" for r in rows)

    def test_dataset_scope_opponent(
        self, run_team_views: Path,
    ) -> None:
        """R4: FURIA dir has shared_matches_vs_primary_team_only scope."""
        furia_csv = run_team_views / "furia" / "maps" / "de_mirage" / "demos.csv"
        rows = list(csv.DictReader(furia_csv.open(encoding="utf-8-sig")))
        assert all(r["dataset_scope"] == "shared_matches_vs_primary_team_only" for r in rows)

    def test_opponent_category_json_scope(
        self, run_team_views: Path,
    ) -> None:
        """R4: category.json for opponent also carries the correct scope."""
        furia_json = run_team_views / "furia" / "maps" / "de_mirage" / "category.json"
        meta = json.loads(furia_json.read_text(encoding="utf-8"))
        assert meta["dataset_scope"] == "shared_matches_vs_primary_team_only"

    # ── R5 ──

    def test_coverage_gaps_csv_created(self, run_team_views: Path) -> None:
        """R5: coverage_gaps.csv exists."""
        gaps = run_team_views / "coverage_gaps.csv"
        assert gaps.is_file()

    def test_coverage_gaps_correct_dedup(
        self, run_team_views: Path,
    ) -> None:
        """R5: coverage counts use unique_demo_candidates, not raw rows."""
        gaps = list(csv.DictReader(
            (run_team_views / "coverage_gaps.csv").open(encoding="utf-8-sig")
        ))
        assert len(gaps) >= 2
        for row in gaps:
            current = int(row["current_unique_matches"])
            assert current >= 1
            assert int(row["minimum_required"]) == 5
            assert int(row["additional_matches_needed"]) == max(0, 5 - current)

    def test_team_map_index_created(self, run_team_views: Path) -> None:
        """Verify team_map_index.csv exists."""
        idx = run_team_views / "team_map_index.csv"
        assert idx.is_file()
        rows = list(csv.DictReader(idx.open(encoding="utf-8-sig")))
        assert len(rows) >= 2  # at least 2 teams * 1+ maps each
