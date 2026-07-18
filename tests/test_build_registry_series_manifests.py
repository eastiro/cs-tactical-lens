"""Tests for scripts/build_registry_series_manifests.py.

Verifies per-team manifest generation from shared import_results.csv.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MANIFEST_SCRIPT = SCRIPTS / "build_registry_series_manifests.py"


def _run_manifest(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MANIFEST_SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    """Simple registry with a few records."""
    reg = {
        "event": "IEM Cologne Major 2026",
        "records": [
            {
                "match_id": "300001", "stage": "stage-3",
                "teams": ["Falcons", "G2"],
                "status": "registered",
            },
            {
                "match_id": "300002", "stage": "stage-3",
                "teams": ["Spirit", "Falcons"],
                "status": "registered",
            },
            {
                "match_id": "400001", "stage": "playoffs",
                "teams": ["Spirit", "G2"],
                "status": "registered",
            },
        ],
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def results_csv(tmp_path: Path) -> Path:
    """import_results.csv with some parsed entries."""
    rows = [
        {"match_id": "300001", "map": "de_dust2", "stage": "stage-3",
         "teams": "Falcons vs G2", "bundle": "../processed/300001/de_dust2",
         "status": "parsed_and_validated"},
        {"match_id": "300002", "map": "de_dust2", "stage": "stage-3",
         "teams": "Spirit vs Falcons", "bundle": "../processed/300002/de_dust2",
         "status": "parsed_and_validated"},
        # Error result → should be excluded
        {"match_id": "400001", "map": "de_dust2", "stage": "playoffs",
         "teams": "Spirit vs G2", "bundle": "",
         "status": "error: extraction failed"},
    ]
    p = tmp_path / "import_results.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["match_id", "map", "stage", "teams", "bundle", "status"])
        w.writeheader()
        w.writerows(rows)
    return p


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "manifests"


# ═════════════════════════════════════════════════════════════════════════
#   Tests
# ═════════════════════════════════════════════════════════════════════════


class TestPerTeamManifests:
    """Each match contributes one entry per team."""

    def test_falcons_and_spirit_manifests(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """Falcons, G2, Spirit each get a manifest (Falcons appears in 2 matches)."""
        result = _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Check which files were created
        created = list(output_dir.iterdir())
        filenames = [p.name for p in created]
        assert "falcons-de_dust2.json" in filenames
        assert "g2-de_dust2.json" in filenames
        assert "spirit-de_dust2.json" in filenames

    def test_falcons_has_two_matches(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """Falcons appears in 300001 and 300002 → 2 entries."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        manifest = json.loads((output_dir / "falcons-de_dust2.json").read_text(encoding="utf-8"))
        assert len(manifest["matches"]) == 2
        match_ids = {m["id"] for m in manifest["matches"]}
        assert match_ids == {"300001", "300002"}

    def test_g2_has_one_match(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """G2 appears in 300001 only → 1 entry."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        manifest = json.loads((output_dir / "g2-de_dust2.json").read_text(encoding="utf-8"))
        assert len(manifest["matches"]) == 1
        assert manifest["matches"][0]["id"] == "300001"


class TestExclusions:
    """Unvalidated or error results must be excluded."""

    def test_error_excluded(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """400001 has status=error → not in any manifest."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        # Spirit should have only 1 match (300002), not 400001
        spirit = json.loads((output_dir / "spirit-de_dust2.json").read_text(encoding="utf-8"))
        match_ids = {m["id"] for m in spirit["matches"]}
        assert "400001" not in match_ids
        assert len(spirit["matches"]) == 1


class TestOpponentMapping:
    """Opponent is correctly determined from registry."""

    def test_correct_opponent(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """Falcons vs G2 → for Falcons, opponent is G2."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        falcons = json.loads((output_dir / "falcons-de_dust2.json").read_text(encoding="utf-8"))
        match_300001 = next(m for m in falcons["matches"] if m["id"] == "300001")
        assert match_300001["opponent"] == "G2"
        match_300002 = next(m for m in falcons["matches"] if m["id"] == "300002")
        assert match_300002["opponent"] == "Spirit"


class TestManifestStructure:
    """Manifest JSON has the required fields."""

    def test_required_fields(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """Each manifest has team, map, season, matches."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        for f in output_dir.iterdir():
            manifest = json.loads(f.read_text(encoding="utf-8"))
            assert "team" in manifest
            assert "map" in manifest
            assert manifest["map"] == "de_dust2"
            assert "matches" in manifest
            for m in manifest["matches"]:
                assert "id" in m
                assert "bundle" in m
                assert "opponent" in m

    def test_bundle_relative_path(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """Bundle path from import_results is preserved."""
        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(results_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        falcons = json.loads((output_dir / "falcons-de_dust2.json").read_text(encoding="utf-8"))
        for m in falcons["matches"]:
            assert m["bundle"].startswith("../processed/")


class TestDedup:
    """Same match_id for a team should not appear twice."""

    def test_no_duplicate_match_ids(self, registry_file: Path, results_csv: Path, output_dir: Path) -> None:
        """If import_results has duplicates, manifest deduplicates by match_id."""
        # Add a duplicate row to results
        dup_csv = results_csv.parent / "import_results_dup.csv"
        with open(results_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        rows.append({
            "match_id": "300001", "map": "de_dust2", "stage": "stage-3",
            "teams": "Falcons vs G2", "bundle": "../processed/300001/de_dust2",
            "status": "parsed_and_validated",
        })
        with open(dup_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

        _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(dup_csv),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        falcons = json.loads((output_dir / "falcons-de_dust2.json").read_text(encoding="utf-8"))
        ids = [m["id"] for m in falcons["matches"]]
        assert len(ids) == len(set(ids))  # no duplicates


class TestCliErrors:
    """Error conditions."""

    def test_missing_results_file(self, registry_file: Path, output_dir: Path) -> None:
        """Non-existent import_results → error."""
        result = _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(output_dir / "nonexistent.csv"),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        assert result.returncode != 0

    def test_no_validated_results(self, registry_file: Path, output_dir: Path) -> None:
        """import_results with only errors → error."""
        output_dir.mkdir(parents=True, exist_ok=True)
        empty = output_dir / "empty_results.csv"
        with empty.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["match_id", "map", "stage", "teams", "bundle", "status"])
            w.writeheader()
            w.writerow({"match_id": "999", "map": "de_dust2", "status": "error: failed"})

        result = _run_manifest(
            "--registry", str(registry_file),
            "--import-results", str(empty),
            "--map", "de_dust2",
            "--output-dir", str(output_dir),
        )
        assert result.returncode != 0
        assert "parsed_and_validated" in result.stderr or "parsed_and_validated" in result.stdout
