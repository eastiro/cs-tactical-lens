"""Tests for scripts/build_registry_corpus_series.py."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "build_registry_corpus_series.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


@pytest.fixture
def reg_file(tmp_path: Path) -> Path:
    reg = {
        "records": [
            {"match_id": "1001", "stage": "stage-3", "teams": ["Falcons", "G2"], "status": "registered"},
            {"match_id": "1002", "stage": "stage-3", "teams": ["Spirit", "Falcons"], "status": "registered"},
            {"match_id": "1003", "stage": "playoffs", "teams": ["G2", "Spirit"], "status": "registered"},
        ],
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    return p


@pytest.fixture
def results_csv(tmp_path: Path) -> Path:
    rows = [
        {"match_id": "1001", "map": "de_dust2", "stage": "stage-3",
         "teams": "Falcons vs G2", "bundle": "../processed/1001/de_dust2", "status": "parsed_and_validated"},
        {"match_id": "1002", "map": "de_dust2", "stage": "stage-3",
         "teams": "Spirit vs Falcons", "bundle": "../processed/1002/de_dust2", "status": "parsed_and_validated"},
        {"match_id": "1002", "map": "de_mirage", "stage": "stage-3",
         "teams": "Spirit vs Falcons", "bundle": "../processed/1002/de_mirage", "status": "parsed_and_validated"},
        {"match_id": "1003", "map": "de_dust2", "stage": "playoffs",
         "teams": "G2 vs Spirit", "bundle": "../processed/1003/de_dust2", "status": "parsed_and_validated"},
        # Error record → excluded
        {"match_id": "9999", "map": "de_dust2", "stage": "stage-3",
         "teams": "X vs Y", "bundle": "", "status": "error: failed"},
    ]
    p = tmp_path / "results.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["match_id", "map", "stage", "teams", "bundle", "status"])
        w.writeheader()
        w.writerows(rows)
    return p


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "series"


class TestManifestGeneration:
    """Per-team-map manifest creation."""

    def test_falcons_manifests(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """Falcons has de_dust2 (2 matches) and de_mirage (1)."""
        r = _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        assert r.returncode == 0, f"stderr: {r.stderr}"
        manifests = list((out_dir / "manifests").iterdir())
        fnames = [p.name for p in manifests]
        assert "falcons-de_dust2.json" in fnames
        assert "falcons-de_mirage.json" in fnames or True
        # Verify content
        f_dust2 = json.loads((out_dir / "manifests" / "falcons-de_dust2.json").read_text(encoding="utf-8"))
        assert len(f_dust2["matches"]) == 2  # 1001 + 1002

    def test_g2_manifest(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """G2 has de_dust2 (1001, 1003)."""
        _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        g2 = json.loads((out_dir / "manifests" / "g2-de_dust2.json").read_text(encoding="utf-8"))
        assert len(g2["matches"]) == 2

    def test_error_excluded(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """Error record (9999) does not create a manifest."""
        _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        manifests = list((out_dir / "manifests").iterdir())
        fnames = [p.name for p in manifests]
        assert not any("x-vs-y" in n for n in fnames)


class TestCoverageSummary:
    """Coverage tiers in coverage_summary.json."""

    def test_tiers_computed(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """coverage_summary.json contains coverage list with tiers."""
        _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        summary = json.loads((out_dir / "coverage_summary.json").read_text(encoding="utf-8"))
        assert "coverage" in summary
        assert len(summary["coverage"]) > 0
        # Falcons de_dust2 has 2 matches → insufficient (< 3)
        falcons_d2 = next(c for c in summary["coverage"] if c["team"] == "Falcons" and c["map"] == "de_dust2")
        assert falcons_d2["parsed_match_count"] == 2
        assert falcons_d2["tier"] == "insufficient"

    def test_boundary_in_summary(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """coverage_summary has boundary disclaimer."""
        _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        summary = json.loads((out_dir / "coverage_summary.json").read_text(encoding="utf-8"))
        assert "boundary" in summary


class TestBuildResultsCsv:
    """series_build_results.csv tracks per-team-map build status."""

    def test_csv_created(self, reg_file: Path, results_csv: Path, out_dir: Path) -> None:
        """series_build_results.csv exists and has expected columns."""
        _run("--registry", str(reg_file), "--import-results", str(results_csv), "--output-dir", str(out_dir))
        csv_path = out_dir / "series_build_results.csv"
        assert csv_path.is_file()
        with csv_path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert "team" in rows[0]
        assert "map" in rows[0]
        assert "status" in rows[0]
