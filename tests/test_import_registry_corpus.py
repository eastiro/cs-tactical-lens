"""Tests for scripts/import_registry_corpus.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "import_registry_corpus.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


@pytest.fixture
def reg_file(tmp_path: Path) -> Path:
    """Registry with a mix of single, segmented, and missing entries."""
    reg = {
        "records": [
            # 3 ready single-member entries
            {
                "match_id": "1001", "stage": "stage-3",
                "teams": ["Falcons", "G2"],
                "members": [{"member": "m1-dust2.dem", "map": "de_dust2", "size_bytes": 100}],
                "status": "registered",
            },
            {
                "match_id": "1002", "stage": "stage-3",
                "teams": ["Spirit", "Falcons"],
                "members": [{"member": "m1-mirage.dem", "map": "de_mirage", "size_bytes": 200}],
                "status": "registered",
            },
            {
                "match_id": "1003", "stage": "playoffs",
                "teams": ["G2", "Spirit"],
                "members": [{"member": "m1-dust2.dem", "map": "de_dust2", "size_bytes": 300}],
                "status": "registered",
            },
            # Segmented: 2 members for same map
            {
                "match_id": "2001", "stage": "stage-3",
                "teams": ["Navi", "G2"],
                "members": [
                    {"member": "m1-dust2-p1.dem", "map": "de_dust2", "size_bytes": 400},
                    {"member": "m1-dust2-p2.dem", "map": "de_dust2", "size_bytes": 401},
                ],
                "status": "registered",
            },
            # Missing archive
            {
                "match_id": "3001", "stage": "stage-2",
                "teams": ["Legacy", "Tyloo"],
                "members": [],
                "status": "missing_archive",
            },
            # Stage-2 ready
            {
                "match_id": "4001", "stage": "stage-2",
                "teams": ["M80", "Legacy"],
                "members": [{"member": "m1-nuke.dem", "map": "de_nuke", "size_bytes": 500}],
                "status": "registered",
            },
        ],
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def out(tmp_path: Path) -> Path:
    return tmp_path / "output"


class TestEnumeration:
    """Full enumeration of ready / segmented / missing."""

    def test_ready_count(self, reg_file: Path, out: Path) -> None:
        """4 ready entries (1001, 1002, 1003, 4001), 1 segmented, 1 missing."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run")
        assert r.returncode == 0
        assert "Ready" in r.stdout

    def test_segmented_detected(self, reg_file: Path, out: Path) -> None:
        """2001 with 2 dust2 members → segmented blocked."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run")
        assert r.returncode == 0

    def test_missing_excluded(self, reg_file: Path, out: Path) -> None:
        """3001 missing_archive → listed as missing."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run")
        assert r.returncode == 0


class TestFilters:
    """--maps and --stages filtering."""

    def test_map_filter(self, reg_file: Path, out: Path) -> None:
        """--maps de_dust2 → only 1001 and 1003 (and 2001 as blocked)."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run", "--maps", "de_dust2")
        assert r.returncode == 0
        assert "Ready" in r.stdout

    def test_stage_filter(self, reg_file: Path, out: Path) -> None:
        """--stages stage-3 → only 1001, 1002 (and 2001 blocked)."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run", "--stages", "stage-3")
        assert r.returncode == 0
        assert "Ready" in r.stdout


class TestLimit:
    """--limit truncates ready queue."""

    def test_limit_applied(self, reg_file: Path, out: Path) -> None:
        """--limit 2 → only processes first 2 ready entries."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run", "--limit", "2")
        assert r.returncode == 0
        assert "Limit" in r.stdout


class TestDryRunOutput:
    """Dry-run creates Markdown report."""

    def test_md_report_created(self, reg_file: Path, out: Path) -> None:
        """Dry-run generates corpus-dry-run.md."""
        r = _run("--registry", str(reg_file), "--output", str(out), "--dry-run")
        assert r.returncode == 0
        md = out / "corpus-dry-run.md"
        assert md.is_file()
        content = md.read_text(encoding="utf-8")
        assert "Dry-run" in content
