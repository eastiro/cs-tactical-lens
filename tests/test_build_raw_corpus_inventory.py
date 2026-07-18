"""Tests for scripts/build_raw_corpus_inventory.py.

Verifies event/stage path extraction, multi-map aggregation, duplicate
detection, unknown maps, and dual JSON+Markdown output.
"""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ── helpers ────────────────────────────────────────────────────────────────


def _run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    """Run one of the scripts/ scripts with *args."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _fake_dem(name: str, size: int = 1024) -> bytes:
    """Deterministic fake .dem content."""
    return (name * 200).encode()[:size]


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    """Create a .zip at *path* containing *members*."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)


def _check_json_report(path: Path) -> dict:
    """Assert report exists and return parsed JSON."""
    assert path.is_file(), f"JSON report missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _check_md_report(path: Path) -> str:
    """Assert markdown report exists and return content."""
    assert path.is_file(), f"Markdown report missing: {path}"
    return path.read_text(encoding="utf-8")


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def events_root(tmp_path: Path) -> Path:
    """Create a fake ``events/`` directory with nested event/stage structure."""
    root = tmp_path / "events"
    root.mkdir()
    return root


@pytest.fixture
def json_out(tmp_path: Path) -> Path:
    return tmp_path / "report.json"


@pytest.fixture
def md_out(tmp_path: Path) -> Path:
    return tmp_path / "report.md"


# ═════════════════════════════════════════════════════════════════════════
#   Tests
# ═════════════════════════════════════════════════════════════════════════


class TestEventStageExtraction:
    """Verify event/stage path parsing from directory structure."""

    def test_three_layer_path(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """events/<event>/<stage>/file.zip → event and stage are captured."""
        d = events_root / "iem-cologne" / "stage-2"
        d.mkdir(parents=True)
        _make_zip(d / "match1.zip", {"mirage.dem": _fake_dem("mirage")})
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        entry = r["archives"][0]
        assert entry["event"] == "iem-cologne"
        assert entry["stage"] == "stage-2"
        assert entry["sub_stage"] is None

    def test_two_layer_path_no_stage(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """events/<event>/file.zip → stage is None."""
        d = events_root / "iem-rio"
        d.mkdir()
        _make_zip(d / "match1.zip", {"mirage.dem": _fake_dem("mirage")})
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        entry = r["archives"][0]
        assert entry["event"] == "iem-rio"
        assert entry["stage"] is None

    def test_four_layer_path_with_sub_stage(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """events/<event>/<stage>/<sub_stage>/file.zip → sub_stage captured."""
        d = events_root / "iem-cologne" / "playoffs" / "single-map-demos"
        d.mkdir(parents=True)
        _make_zip(d / "demo.zip", {"mirage.dem": _fake_dem("mirage")})
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        entry = r["archives"][0]
        assert entry["event"] == "iem-cologne"
        assert entry["stage"] == "playoffs"
        assert entry["sub_stage"] == "single-map-demos"


class TestAggregation:
    """Multi-map, per-event, and per-stage aggregation."""

    def test_multi_map_archive(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """ZIP with 3 maps → all three recognised in priority table."""
        d = events_root / "event-a" / "stage-1"
        d.mkdir(parents=True)
        _make_zip(d / "bo3.zip", {
            "m1-mirage.dem": _fake_dem("mirage"),
            "m2-dust2.dem": _fake_dem("dust2"),
            "m3-inferno.dem": _fake_dem("inferno"),
        })
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        assert r["total_archives"] == 1
        assert r["total_members"] == 3
        # Priority table should have 3 rows for this event/stage
        candidates = [c for c in r["priority_candidates"]
                      if c["event"] == "event-a"]
        assert len(candidates) == 3
        maps_found = {c["map"] for c in candidates}
        assert maps_found == {"de_mirage", "de_dust2", "de_inferno"}
        assert all(c["raw_candidate_count"] == 1 for c in candidates)

    def test_multiple_events_separate_counts(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Files under different events are counted separately."""
        for evt in ("event-a", "event-b"):
            d = events_root / evt
            d.mkdir()
            _make_zip(d / f"{evt}-match.zip", {"mirage.dem": _fake_dem("mirage")})
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        assert r["total_archives"] == 2
        assert r["total_members"] == 2
        assert len(r["events"]) == 2

    def test_single_dem_file(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """A bare .dem file is inventoried correctly."""
        d = events_root / "some-event"
        d.mkdir()
        (d / "team-a-vs-team-b-m1-mirage.dem").write_bytes(_fake_dem("mirage"))
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        assert r["total_archives"] == 1
        assert r["total_members"] == 1
        assert r["archives"][0]["members"][0]["map"] == "de_mirage"


class TestUnknownMap:
    """Unidentifiable member filenames must be flagged."""

    def test_unknown_map_detected(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Member with unrecognisable name → map=unknown."""
        d = events_root / "scrim" / "stage-1"
        d.mkdir(parents=True)
        _make_zip(d / "session.zip", {"round1.dem": _fake_dem("round1")})
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        assert r["unknown_map_count"] >= 1
        unknowns = [m for a in r["archives"] for m in a["members"] if m["map"] == "unknown"]
        assert len(unknowns) >= 1


class TestDuplicates:
    """Duplicate detection across archives."""

    def test_duplicate_candidates(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Same member name+size across archives → duplicate_candidate_count > 0."""
        # Same filename and same content = same size → duplicate
        for i in range(2):
            d = events_root / f"dup-event-{i}" / "stage-A"
            d.mkdir(parents=True)
            (d / "match-mirage.dem").write_bytes(_fake_dem("mirage", 1024))
        _run_script("build_raw_corpus_inventory.py", str(events_root), "--output", str(json_out), "--markdown", str(md_out))
        r = _check_json_report(json_out)
        assert r["duplicate_candidate_count"] >= 1


class TestOutput:
    """Ensure both JSON and Markdown are generated."""

    def test_both_outputs_created(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Both --output and --markdown files are produced."""
        d = events_root / "test-event"
        d.mkdir()
        (d / "mirage.dem").write_bytes(_fake_dem("mirage"))
        result = _run_script(
            "build_raw_corpus_inventory.py", str(events_root),
            "--output", str(json_out), "--markdown", str(md_out),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # JSON
        r = _check_json_report(json_out)
        assert "inventory_timestamp" in r
        assert "priority_candidates" in r
        assert "boundary" in r
        assert "archives" in r
        # Markdown
        md = _check_md_report(md_out)
        assert "Raw Corpus" in md
        assert "可优先导入候选" in md
        assert "未解析任何 demo 内容" in md

    def test_output_parent_auto_created(self, events_root: Path, tmp_path: Path) -> None:
        """Output parent does not exist → created automatically."""
        d = events_root / "evt"
        d.mkdir()
        (d / "mirage.dem").write_bytes(_fake_dem("mirage"))
        deep_json = tmp_path / "a" / "b" / "out.json"
        deep_md = tmp_path / "a" / "b" / "out.md"
        result = _run_script(
            "build_raw_corpus_inventory.py", str(events_root),
            "--output", str(deep_json), "--markdown", str(deep_md),
        )
        assert result.returncode == 0
        assert deep_json.is_file()
        assert deep_md.is_file()


class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_events_dir(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Empty events directory → non-zero exit."""
        result = _run_script(
            "build_raw_corpus_inventory.py", str(events_root),
            "--output", str(json_out), "--markdown", str(md_out),
        )
        assert result.returncode != 0

    def test_no_demo_files_in_events(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Events with non-demo files only → non-zero exit."""
        d = events_root / "event-a" / "stage-1"
        d.mkdir(parents=True)
        (d / "readme.txt").write_text("not a demo")
        result = _run_script(
            "build_raw_corpus_inventory.py", str(events_root),
            "--output", str(json_out), "--markdown", str(md_out),
        )
        assert result.returncode != 0

    def test_boundary_in_output(self, events_root: Path, json_out: Path, md_out: Path) -> None:
        """Both JSON and Markdown contain the boundary disclaimer."""
        d = events_root / "evt"
        d.mkdir()
        (d / "mirage.dem").write_bytes(_fake_dem("mirage"))
        _run_script(
            "build_raw_corpus_inventory.py", str(events_root),
            "--output", str(json_out), "--markdown", str(md_out),
        )
        r = _check_json_report(json_out)
        assert "boundary" in r
        assert "仅基于文件名" in r["boundary"]
        md = _check_md_report(md_out)
        assert "仅基于文件名" in md
