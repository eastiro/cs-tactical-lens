"""Tests for scripts/preflight_demo_archives.py.

These tests verify the preflight checker against fake archives without
requiring 7-Zip or touching real demo files.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers (borrowed pattern from test_catalog_scripts.py) ────────────────


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


def _load_report(path: Path) -> dict:
    """Load the preflight JSON report and assert basic structure exists."""
    assert path.is_file(), f"report not created at {path}"
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """A temporary directory with a mix of .dem and .zip files."""
    d = tmp_path / "raw"
    d.mkdir()
    return d


@pytest.fixture
def single_dem_source(source_dir: Path) -> Path:
    """Just one bare .dem with a recognizable map name."""
    (source_dir / "falcons-vs-furia-m1-mirage.dem").write_bytes(_fake_dem("mirage"))
    return source_dir


@pytest.fixture
def mixed_source(source_dir: Path) -> Path:
    """Bare .dem + zip with 3 maps + zip with unknown map name."""
    # Bare .dem
    (source_dir / "falcons-vs-furia-m1-mirage.dem").write_bytes(_fake_dem("mirage"))

    # ZIP with 3 known maps
    _make_zip(source_dir / "falcons-vs-spirit-bo3.zip", {
        "falcons-vs-spirit-m1-mirage.dem": _fake_dem("mirage"),
        "spirit-vs-falcons-m2-dust2.dem": _fake_dem("dust2"),
        "spirit-vs-falcons-m3-inferno.dem": _fake_dem("inferno"),
    })

    # ZIP with an unidentifiable map name
    _make_zip(source_dir / "random-scrim.zip", {
        "scrim-round-01.dem": _fake_dem("round1"),
    })

    return source_dir


@pytest.fixture
def duplicate_source(source_dir: Path) -> Path:
    """Two sources whose members share the same filename+size → duplicate key."""
    # Bare .dem
    (source_dir / "fnatic-vs-navi-m1-mirage.dem").write_bytes(_fake_dem("mirage"))
    # Same .dem in a zip → same filename + same 1024 bytes → duplicate candidate
    _make_zip(source_dir / "fnatic-vs-navi-bo3.zip", {
        "fnatic-vs-navi-m1-mirage.dem": _fake_dem("mirage"),
    })
    return source_dir


@pytest.fixture
def rar_without_7zip_source(source_dir: Path) -> Path:
    """A .rar file alongside valid entries; environment may lack 7-Zip."""
    # Place a .rar (valid entries can still be checked)
    (source_dir / "some-match-bo3.rar").write_bytes(b"fake rar content")
    # Also a bare .dem that should still be processed
    (source_dir / "team-a-vs-team-b-m1-dust2.dem").write_bytes(_fake_dem("dust2"))
    return source_dir


@pytest.fixture
def output_report(tmp_path: Path) -> Path:
    """Default report path (parent does NOT exist yet for auto-create test)."""
    return tmp_path / "reports" / "preflight.json"


# ═════════════════════════════════════════════════════════════════════════
#   Tests: preflight_demo_archives.py
# ═════════════════════════════════════════════════════════════════════════


class TestPreflightBasic:
    """Bare .dem and basic output structure."""

    def test_bare_dem_output_created(self, single_dem_source: Path, output_report: Path) -> None:
        """Runs without error and produces a valid JSON report."""
        result = _run_script(
            "preflight_demo_archives.py",
            str(single_dem_source),
            "--output", str(output_report),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        report = _load_report(output_report)
        assert "archives" in report
        assert "summary" in report
        assert "preflight_timestamp" in report

    def test_bare_dem_content(self, single_dem_source: Path, output_report: Path) -> None:
        """Single bare .dem → 1 archive, 1 member, map=de_mirage."""
        _run_script(
            "preflight_demo_archives.py",
            str(single_dem_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        assert len(report["archives"]) == 1
        assert report["summary"]["total_members"] == 1
        members = report["archives"][0]["members"]
        assert len(members) == 1
        assert members[0]["map"] == "de_mirage"
        assert members[0]["duplicate_key"] == "falcons-vs-furia-m1-mirage.dem::1024"

    def test_map_detection(self, single_dem_source: Path, output_report: Path) -> None:
        """Map name is correctly identified from member filename."""
        _run_script(
            "preflight_demo_archives.py",
            str(single_dem_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        assert report["summary"]["maps"].get("de_mirage", 0) == 1
        assert report["summary"]["unknown_map_count"] == 0


class TestPreflightZip:
    """ZIP archives with multiple members."""

    def test_zip_multiple_maps(self, mixed_source: Path, output_report: Path) -> None:
        """Zip with 3 demos → all 3 maps detected."""
        _run_script(
            "preflight_demo_archives.py",
            str(mixed_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        maps = report["summary"]["maps"]
        # 1 bare mirage + 3 from zip + 1 unknown from random-scrim
        assert maps.get("de_mirage", 0) == 2  # bare + zip
        assert maps.get("de_dust2", 0) == 1
        assert maps.get("de_inferno", 0) == 1

    def test_unknown_map_detected(self, mixed_source: Path, output_report: Path) -> None:
        """Unidentifiable member filename → map=unknown."""
        _run_script(
            "preflight_demo_archives.py",
            str(mixed_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        assert report["summary"]["unknown_map_count"] == 1
        # Find the unknown member
        unknowns = [
            m for a in report["archives"] for m in a["members"] if m["map"] == "unknown"
        ]
        assert len(unknowns) == 1
        assert "scrim-round-01" in unknowns[0]["member"]

    def test_zip_no_dem_members(self, source_dir: Path, output_report: Path) -> None:
        """Zip with no .dem members is still listed but with zero members."""
        _make_zip(source_dir / "empty-dump.zip", {
            "readme.txt": b"not a demo",
            "metadata.json": b"{}",
        })
        _run_script(
            "preflight_demo_archives.py",
            str(source_dir),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        empty_zips = [a for a in report["archives"] if len(a["members"]) == 0]
        assert len(empty_zips) == 1


class TestPreflightDuplicates:
    """Duplicate-key detection across multiple sources."""

    def test_duplicate_candidates_detected(self, duplicate_source: Path, output_report: Path) -> None:
        """Same filename+size across archives → duplicate_candidate_count > 0."""
        _run_script(
            "preflight_demo_archives.py",
            str(duplicate_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        assert report["summary"]["duplicate_candidate_count"] >= 1

    def test_no_false_duplicate(self, mixed_source: Path, output_report: Path) -> None:
        """Different filenames across entries → no duplicate candidates."""
        _run_script(
            "preflight_demo_archives.py",
            str(mixed_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        # Every .dem in mixed_source has a distinct filename → no overlaps
        assert report["summary"]["duplicate_candidate_count"] == 0


class TestPreflightOutputDir:
    """Auto-creation of output parent directory."""

    def test_output_parent_auto_created(self, single_dem_source: Path, tmp_path: Path) -> None:
        """Output parent directory does not exist → is created automatically."""
        deep = tmp_path / "does" / "not" / "exist" / "yet" / "report.json"
        assert not deep.parent.is_dir()
        result = _run_script(
            "preflight_demo_archives.py",
            str(single_dem_source),
            "--output", str(deep),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert deep.parent.is_dir()
        assert deep.is_file()
        _load_report(deep)  # valid JSON


class TestPreflightRarNo7Zip:
    """Graceful handling when 7-Zip is not available for .rar/.7z."""

    def test_rar_without_7zip_graceful(self, rar_without_7zip_source: Path, output_report: Path) -> None:
        """.rar without 7-Zip (or with 7-Zip but corrupt content) → no crash, other entries ok."""
        result = _run_script(
            "preflight_demo_archives.py",
            str(rar_without_7zip_source),
            "--output", str(output_report),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        report = _load_report(output_report)

        # The .rar entry should have a non-"ok" status (needs_7zip or enumeration_error)
        rar_archives = [a for a in report["archives"] if a["archive_suffix"] == ".rar"]
        assert len(rar_archives) == 1
        assert rar_archives[0]["enumerate_status"] != "ok"
        assert rar_archives[0]["error_message"] is not None

        # Non-.rar entries are still fully processed regardless
        dem_archives = [a for a in report["archives"] if a["archive_suffix"] == ".dem"]
        assert len(dem_archives) == 1
        assert dem_archives[0]["enumerate_status"] == "ok"
        assert dem_archives[0]["members"][0]["map"] == "de_dust2"

        # Summary exists and total reflects all sources
        assert report["summary"]["total_archives"] == 2
        assert report["summary"]["total_members"] >= 1  # at least the bare .dem


class TestPreflightEdgeCases:
    """Boundary conditions."""

    def test_empty_directory(self, source_dir: Path, output_report: Path) -> None:
        """No demo files → non-zero exit and no report created."""
        result = _run_script(
            "preflight_demo_archives.py",
            str(source_dir),
            "--output", str(output_report),
        )
        assert result.returncode != 0
        # stdout/stderr check: subprocess encoding may garble Chinese on Windows,
        # so only assert return code and that report was NOT created
        assert not output_report.is_file()

    def test_no_dem_files_only_other(self, source_dir: Path, output_report: Path) -> None:
        """Directory with non-demo files only → non-zero exit."""
        (source_dir / "notes.txt").write_text("hello")
        result = _run_script(
            "preflight_demo_archives.py",
            str(source_dir),
            "--output", str(output_report),
        )
        assert result.returncode != 0
        assert not output_report.is_file()

    def test_source_is_file_not_dir(self, tmp_path: Path, output_report: Path) -> None:
        """Source is a file, not a directory → error."""
        f = tmp_path / "my.dem"
        f.write_bytes(b"not-really-a-demo")
        result = _run_script(
            "preflight_demo_archives.py",
            str(f),
            "--output", str(output_report),
        )
        assert result.returncode != 0
        # Error text may be garbled on Windows due to encoding mismatch
        # so check the return code and non-empty stderr instead
        assert len(result.stderr) > 0 or len(result.stdout) > 0

    def test_summary_boundary_present(self, single_dem_source: Path, output_report: Path) -> None:
        """Summary includes the required boundary disclaimer."""
        _run_script(
            "preflight_demo_archives.py",
            str(single_dem_source),
            "--output", str(output_report),
        )
        report = _load_report(output_report)
        assert "boundary" in report["summary"]
        assert "仅基于文件名" in report["summary"]["boundary"]
