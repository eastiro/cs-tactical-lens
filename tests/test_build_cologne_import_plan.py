"""Tests for scripts/build_cologne_import_plan.py.

Uses a fake registry to verify coverage computation, deduplication,
threshold-based recommendations, and output generation.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _run_script(registry_path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    base = [
        sys.executable, str(SCRIPTS / "build_cologne_import_plan.py"),
        "--registry", str(registry_path),
    ]
    return subprocess.run(
        [*base, *extra_args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _read_json(path: Path) -> dict:
    assert path.is_file(), f"missing {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    """Create a fake registry JSON for testing."""
    reg = {
        "event": "IEM Cologne Major 2026",
        "total_match_ids": 8,
        "summary": {"registered": 7, "missing_archive": 1, "ambiguous_archive": 0},
        "records": [
            # Registered records with multiple maps
            {
                "match_id": "1001", "stage": "stage-3",
                "teams": ["Falcons", "G2"],
                "members": [
                    {"member": "m1-mirage.dem", "map": "de_mirage", "size_bytes": 100},
                    {"member": "m2-dust2.dem", "map": "de_dust2", "size_bytes": 101},
                ],
                "status": "registered",
            },
            {
                "match_id": "1002", "stage": "stage-3",
                "teams": ["Spirit", "Falcons"],
                "members": [
                    {"member": "m1-mirage.dem", "map": "de_mirage", "size_bytes": 200},
                    {"member": "m2-dust2.dem", "map": "de_dust2", "size_bytes": 201},
                ],
                "status": "registered",
            },
            {
                "match_id": "1003", "stage": "stage-3",
                "teams": ["Spirit", "G2"],
                "members": [
                    {"member": "m1-dust2.dem", "map": "de_dust2", "size_bytes": 300},
                ],
                "status": "registered",
            },
            # Stage-2 record (should not affect first-cohort recommendations)
            {
                "match_id": "2001", "stage": "stage-2",
                "teams": ["Falcons", "M80"],
                "members": [
                    {"member": "m1-mirage.dem", "map": "de_mirage", "size_bytes": 400},
                ],
                "status": "registered",
            },
            # Record with p1/p2 split (same map twice → dedup to 1)
            {
                "match_id": "1004", "stage": "stage-3",
                "teams": ["G2", "Natus Vincere"],
                "members": [
                    {"member": "m1-mirage-p1.dem", "map": "de_mirage", "size_bytes": 500},
                    {"member": "m1-mirage-p2.dem", "map": "de_mirage", "size_bytes": 501},
                ],
                "status": "registered",
            },
            # Playoffs record
            {
                "match_id": "3001", "stage": "playoffs",
                "teams": ["Falcons", "Spirit"],
                "members": [
                    {"member": "m1-mirage.dem", "map": "de_mirage", "size_bytes": 600},
                    {"member": "m2-dust2.dem", "map": "de_dust2", "size_bytes": 601},
                ],
                "status": "registered",
            },
            # Missing archive record
            {
                "match_id": "4001", "stage": "stage-2",
                "teams": ["Legacy", "Tyloo"],
                "members": [],
                "status": "missing_archive",
            },
        ],
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def json_out(tmp_path: Path) -> Path:
    return tmp_path / "plan.json"


@pytest.fixture
def md_out(tmp_path: Path) -> Path:
    return tmp_path / "plan.md"


# ═════════════════════════════════════════════════════════════════════════
#   Tests
# ═════════════════════════════════════════════════════════════════════════


class TestOnlyRegistered:
    """Only registered records must be included."""

    def test_missing_excluded(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Missing-archive record is not counted in coverage."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        assert p["summary"]["total_registered_matches"] == 6
        assert p["summary"]["total_missing_matches"] == 1
        # The missing team (Legacy, Tyloo) should NOT appear in team_map_rows
        all_teams = {r["team"] for r in p["all_registered_coverage"]["team_map_rows"]}
        assert "Legacy" not in all_teams
        assert "Tyloo" not in all_teams


class TestDedup:
    """p1/p2 split members must be deduplicated."""

    def test_p1_p2_dedup(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Match 1004 has two members with map=de_mirage → counted as 1."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        # 7 registered records but some have split maps
        # Total raw: 1001(2) + 1002(2) + 1003(1) + 2001(1) + 1004(2) + 3001(2) = 10
        # After dedup: 1001(2) + 1002(2) + 1003(1) + 2001(1) + 1004(1) + 3001(2) = 9
        assert p["summary"]["total_raw_members"] == 10
        assert p["summary"]["total_dedup_map_samples"] == 9


class TestTeamMap:
    """Each match contributes two team-map candidates."""

    def test_team_map_count(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Falcons appears in 4 registered matches: 1001, 1002, 2001, 3001."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        # Check Falcons coverage in all registered
        falcons_rows = [
            r for r in p["all_registered_coverage"]["team_map_rows"]
            if r["team"] == "Falcons"
        ]
        falcons_mirage = next(r for r in falcons_rows if r["map"] == "de_mirage")
        # Falcons on mirage: 1001(vs G2), 1002(vs Spirit), 2001(vs M80), 3001(vs Spirit) = 4
        assert falcons_mirage["distinct_match_count"] == 4
        # Stage breakdown for Falcons/Mirage
        assert falcons_mirage["stage_breakdown"].get("stage-2", 0) == 1
        assert falcons_mirage["stage_breakdown"].get("stage-3", 0) == 2
        assert falcons_mirage["stage_breakdown"].get("playoffs", 0) == 1


class TestStageBreakdown:
    """Stage breakdown must be correct."""

    def test_stage_counts(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Breakdown: stage-2(1 match), stage-3(4), playoffs(1), missing ignored."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        sb = p["summary"]["stage_breakdown"]
        assert sb["stage-2"]["registered_matches"] == 1
        assert sb["stage-3"]["registered_matches"] == 4
        assert sb["playoffs"]["registered_matches"] == 1
        # stage-2 dedup: only 2001 with 1 member = 1
        assert sb["stage-2"]["dedup_map_samples"] == 1
        # stage-3 dedup: 1001(2) + 1002(2) + 1003(1) + 1004(1 deduped) = 6
        assert sb["stage-3"]["dedup_map_samples"] == 6
        # playoffs dedup: 3001(2) = 2
        assert sb["playoffs"]["dedup_map_samples"] == 2


class TestRecommendations:
    """Threshold-based first cohort recommendations."""

    def test_standard_threshold_5(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Stage-3 + Playoffs: Falcons(4) + Spirit(3) on mirage, but no 5+ pair → no standard."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        recs = p["recommended_first_cohort"]
        # Only de_dust2 has 2+ teams with >= 5 in stage-3+playoffs?
        # Let's check the coverage first
        p["stage3_playoffs_coverage"]
        # Falcons dust2 in s3p: 1001(vs G2), 1002(vs Spirit), 3001(vs Spirit) = 3
        # Spirit dust2 in s3p: 1002(vs Falcons), 1003(vs G2), 3001(vs Falcons) = 3
        # G2 dust2 in s3p: 1001(vs Falcons), 1003(vs Spirit) = 2
        # So no team has >=5 in s3p + playoffs → all recommendations should be exploratory
        assert all(r["tier"] == "exploratory" for r in recs)
        # Should still recommend something (>= 3 threshold)
        assert len(recs) >= 1

    def test_exploratory_fallback(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """When no pair reaches 5 + 5, fallback to 3+ exploratory."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        recs = p["recommended_first_cohort"]
        # Check that at least one recommendation mentions 'exploratory' in rationale
        exploratory = [r for r in recs if r["tier"] == "exploratory"]
        assert len(exploratory) >= 1
        # Rationale should mention the fallback
        assert "exploratory" in exploratory[0]["rationale"].lower() or "暂无双队" in exploratory[0]["rationale"]

    def test_recommendation_structure(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Each recommendation has required fields."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        for rec in p["recommended_first_cohort"]:
            assert "map" in rec
            assert "tier" in rec
            assert "teams" in rec
            assert len(rec["teams"]) >= 2
            assert "total_unique_matches" in rec
            assert "related_match_ids" in rec
            assert "rationale" in rec
            assert "limitations" in rec


class TestOutput:
    """JSON and Markdown output."""

    def test_markdown_contains_key_sections(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """Markdown report contains all required sections."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        md = md_out.read_text(encoding="utf-8")
        assert "解析批次规划" in md
        assert "全量覆盖" in md
        assert "Stage 3 + Playoffs" in md
        assert "推荐第一批" in md
        assert "仅基于注册表" in md

    def test_json_contains_key_sections(self, registry_file: Path, json_out: Path, md_out: Path) -> None:
        """JSON has all required top-level keys."""
        _run_script(registry_file, "--output", str(json_out), "--report", str(md_out))
        p = _read_json(json_out)
        for key in ("event", "source_registry", "scope", "summary",
                     "all_registered_coverage", "stage3_playoffs_coverage",
                     "recommended_first_cohort"):
            assert key in p, f"missing key: {key}"

    def test_cli_requires_all_args(self, registry_file: Path) -> None:
        """Missing --output should fail."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "build_cologne_import_plan.py"),
             "--registry", str(registry_file)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
