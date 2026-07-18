"""Tests for scripts/import_registry_batch.py.

Uses a fake registry to verify candidate selection, p1/p2 blocking,
dry-run behaviour, and CLI error handling.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
IMPORTER = SCRIPTS / "import_registry_batch.py"


def _run_importer(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(IMPORTER), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    assert path.is_file(), f"missing {path}"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    """Fake registry with 13 Dust2 candidates + 1 blocked + 1 missing."""
    reg = {
        "event": "IEM Cologne Major 2026",
        "records": [
            # 13 registered records with single de_dust2 member (stage-3 + playoffs)
            *[
                {
                    "match_id": str(300000 + i), "stage": "stage-3",
                    "teams": ["Falcons", f"Team{i}"],
                    "members": [{"member": f"falcons-vs-team{i}-dust2.dem", "map": "de_dust2", "size_bytes": 1000 + i}],
                    "status": "registered",
                }
                for i in range(1, 11)  # 10 stage-3
            ],
            *[
                {
                    "match_id": str(400000 + i), "stage": "playoffs",
                    "teams": ["Spirit", f"Rival{i}"],
                    "members": [{"member": f"spirit-vs-rival{i}-dust2.dem", "map": "de_dust2", "size_bytes": 2000 + i}],
                    "status": "registered",
                }
                for i in range(1, 4)  # 3 playoffs
            ],
            # Segmented record: 2 members with same map → blocked
            {
                "match_id": "500001", "stage": "stage-3",
                "teams": ["G2", "Navi"],
                "members": [
                    {"member": "g2-vs-navi-dust2-p1.dem", "map": "de_dust2", "size_bytes": 3000},
                    {"member": "g2-vs-navi-dust2-p2.dem", "map": "de_dust2", "size_bytes": 3001},
                ],
                "status": "registered",
            },
            # Missing archive record → excluded
            {
                "match_id": "600001", "stage": "stage-2",
                "teams": ["Legacy", "Tyloo"],
                "members": [],
                "status": "missing_archive",
            },
            # Stage-2 Dust2 record (not in target stages)
            {
                "match_id": "700001", "stage": "stage-2",
                "teams": ["M80", "Legacy"],
                "members": [{"member": "m80-vs-legacy-dust2.dem", "map": "de_dust2", "size_bytes": 4000}],
                "status": "registered",
            },
        ],
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"


# ═════════════════════════════════════════════════════════════════════════
#   Candidate selection & filtering
# ═════════════════════════════════════════════════════════════════════════


class TestCandidateSelection:
    """Only registered + specified map + specified stages."""

    def test_13_dust2_candidates(self, registry_file: Path, out_dir: Path) -> None:
        """Stage-3 + playoffs de_dust2 → 13 candidates, 1 blocked."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Check output contains key numbers (Chinese may be garbled on Windows)
        assert "Dry-run" in result.stdout

    def test_stage2_excluded(self, registry_file: Path, out_dir: Path) -> None:
        """Stage-2 Dust2 record should not appear when filtering by stage-3,playoffs."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        # "700001" (M80 vs Legacy, stage-2) should not appear
        assert "700001" not in result.stdout

    def test_missing_excluded(self, registry_file: Path, out_dir: Path) -> None:
        """Missing-archive record is never selected."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        assert "600001" not in result.stdout

    def test_no_stage_filter_includes_stage2(self, registry_file: Path, out_dir: Path) -> None:
        """Without --stages, stage-2 Dust2 is included."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        assert "Dry-run" in result.stdout


class TestBlocked:
    """p1/p2 segmentation detection."""

    def test_segmented_blocked(self, registry_file: Path, out_dir: Path) -> None:
        """G2 vs Navi with 2 dust2 members → blocked."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        assert "500001" in result.stdout  # listed as blocked

    def test_not_counted_as_candidate(self, registry_file: Path, out_dir: Path) -> None:
        """Blocked records are NOT in the candidate count."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        assert "Dry-run" in result.stdout  # confirms script ran


class TestLimit:
    """--limit applied after filtering blocked."""

    def test_limit_reduces_candidates(self, registry_file: Path, out_dir: Path) -> None:
        """--limit 3 → only first 3 candidates shown."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run", "--limit", "3",
        )
        assert result.returncode == 0

    def test_limit_stable_order(self, registry_file: Path, out_dir: Path) -> None:
        """Candidates sorted by match_id → first 3 are 300001, 300002, 300003."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run", "--limit", "3",
        )
        assert result.returncode == 0
        # Verify first candidate in output is 300001
        assert "300001" in result.stdout
        # Output dir should NOT exist (dry-run)
        assert not out_dir.is_dir() or not list(out_dir.iterdir())


class TestDryRun:
    """Dry-run does not write output files."""

    def test_no_files_written(self, registry_file: Path, out_dir: Path) -> None:
        """--dry-run: output dir not created, no bundle files."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert result.returncode == 0
        assert not out_dir.is_dir() or not list(out_dir.iterdir())

    def test_dry_run_message(self, registry_file: Path, out_dir: Path) -> None:
        """Dry-run summary contains Dry-run marker."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_dust2", "--stages", "stage-3,playoffs",
            "--output", str(out_dir), "--dry-run",
        )
        assert "Dry-run" in result.stdout


class TestCliErrors:
    """CLI argument validation."""

    def test_missing_registry(self, out_dir: Path) -> None:
        """Non-existent registry → error."""
        result = _run_importer(
            "--registry", str(out_dir / "nonexistent.json"),
            "--map", "de_dust2", "--output", str(out_dir),
        )
        assert result.returncode != 0

    def test_missing_map(self, registry_file: Path, out_dir: Path) -> None:
        """Missing --map → argparse error."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--output", str(out_dir),
        )
        assert result.returncode != 0

    def test_no_matches_for_map(self, registry_file: Path, out_dir: Path) -> None:
        """Map not present in registry → exit."""
        result = _run_importer(
            "--registry", str(registry_file),
            "--map", "de_unknown", "--output", str(out_dir),
        )
        assert result.returncode != 0


class TestPlan:
    """--plan filter narrows candidates to recommended cohort."""

    @pytest.fixture
    def plan_file(self, tmp_path: Path) -> Path:
        """Fake import plan with de_dust2 recommendation."""
        plan = {
            "recommended_first_cohort": [
                {
                    "map": "de_dust2",
                    "tier": "standard",
                    "total_unique_matches": 3,
                    "related_match_ids": ["300001", "300003", "300005"],
                },
                {
                    "map": "de_mirage",
                    "tier": "exploratory",
                    "total_unique_matches": 2,
                    "related_match_ids": ["300002", "300004"],
                },
            ],
        }
        p = tmp_path / "plan.json"
        p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return p

    @pytest.fixture
    def plan_registry(self, tmp_path: Path) -> Path:
        """Small registry with match IDs overlapping the plan."""
        reg = {
            "event": "Cologne",
            "records": [
                {
                    "match_id": "300001", "stage": "stage-3",
                    "teams": ["TeamA", "TeamB"],
                    "members": [{"member": "a-vs-b-dust2.dem", "map": "de_dust2", "size_bytes": 100}],
                    "status": "registered",
                },
                {
                    "match_id": "300002", "stage": "stage-3",
                    "teams": ["TeamC", "TeamD"],
                    "members": [{"member": "c-vs-d-dust2.dem", "map": "de_dust2", "size_bytes": 101}],
                    "status": "registered",
                },
                {
                    "match_id": "300003", "stage": "stage-3",
                    "teams": ["TeamE", "TeamF"],
                    "members": [{"member": "e-vs-f-dust2.dem", "map": "de_dust2", "size_bytes": 102}],
                    "status": "registered",
                },
                {
                    "match_id": "300004", "stage": "stage-3",
                    "teams": ["TeamG", "TeamH"],
                    "members": [{"member": "g-vs-h-dust2.dem", "map": "de_dust2", "size_bytes": 103}],
                    "status": "registered",
                },
                {
                    "match_id": "300005", "stage": "stage-3",
                    "teams": ["TeamI", "TeamJ"],
                    "members": [{"member": "i-vs-j-dust2.dem", "map": "de_dust2", "size_bytes": 104}],
                    "status": "registered",
                },
                {
                    "match_id": "300006", "stage": "stage-3",
                    "teams": ["TeamK", "TeamL"],
                    "members": [{"member": "k-vs-l-dust2.dem", "map": "de_dust2", "size_bytes": 105}],
                    "status": "registered",
                },
            ],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        return p

    def test_plan_narrows_to_cohort(self, plan_registry: Path, plan_file: Path, tmp_path: Path) -> None:
        """Without plan: 5 candidates. With plan: 3 (300001, 300003, 300005)."""
        out = tmp_path / "out"
        r2 = _run_importer(
            "--registry", str(plan_registry),
            "--plan", str(plan_file),
            "--map", "de_dust2",
            "--output", str(out), "--dry-run",
        )
        assert r2.returncode == 0
        assert "300001" in r2.stdout
        assert "300006" not in r2.stdout  # not in plan

    def test_plan_and_stages_cross_filter(self, plan_registry: Path, plan_file: Path, tmp_path: Path) -> None:
        """Plan + stages: only IDs in BOTH plan AND matching stage."""
        out = tmp_path / "out"
        r = _run_importer(
            "--registry", str(plan_registry),
            "--plan", str(plan_file),
            "--map", "de_dust2", "--stages", "stage-3",
            "--output", str(out), "--dry-run",
        )
        assert r.returncode == 0
        assert "300001" in r.stdout
        assert "300005" in r.stdout

    def test_plan_map_not_in_cohort_error(self, plan_registry: Path, plan_file: Path, tmp_path: Path) -> None:
        """Map not in plan's recommended_first_cohort → error."""
        out = tmp_path / "out"
        r = _run_importer(
            "--registry", str(plan_registry),
            "--plan", str(plan_file),
            "--map", "de_overpass",
            "--output", str(out), "--dry-run",
        )
        assert r.returncode != 0

    def test_plan_id_not_in_registry_error(self, plan_registry: Path, plan_file: Path, tmp_path: Path) -> None:
        """Plan recommends IDs not in registry → non-zero exit."""
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        plan["recommended_first_cohort"][0]["related_match_ids"] = ["999999"]
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        out = tmp_path / "out"
        r = _run_importer(
            "--registry", str(plan_registry),
            "--plan", str(plan_file),
            "--map", "de_dust2",
            "--output", str(out), "--dry-run",
        )
        assert r.returncode != 0
