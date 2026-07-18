"""Tests for scripts/build_cologne_match_registry.py.

Uses fake seed data, PLAYOFFS, and inventory to verify binding logic.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = SCRIPTS.parent


def _run_script(fake_corpus: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Run the registry script with --seed and --download-script pointing to fake_corpus."""
    base = [
        str(SCRIPTS / "build_cologne_match_registry.py"),
        "--seed", str(fake_corpus / "data" / "intake-seeds" / "iem-cologne-major-2026-stage2-stage3-match-pages.json"),
        "--download-script", str(fake_corpus / "scripts" / "download_cologne_major_2026.py"),
    ]
    return subprocess.run(
        [sys.executable, *base, *extra_args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _read_json(path: Path) -> dict:
    assert path.is_file(), f"missing {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_corpus(tmp_path: Path) -> Path:
    """Create a fake project root with seed, PLAYOFFS, and inventory."""
    root = tmp_path / "project"
    root.mkdir()

    # data/intake-seeds/
    (root / "data" / "intake-seeds").mkdir(parents=True)
    seed = {
        "schema_version": 1,
        "event": "IEM Cologne Major 2026",
        "stages": {
            "stage_2": [
                {"match_id": "200001", "teams": "Spirit vs 9z",
                 "url": "https://www.hltv.org/matches/200001/spirit-vs-9z-stage-2"},
                {"match_id": "200002", "teams": "Astralis vs Spirit",
                 "url": "https://www.hltv.org/matches/200002/astralis-vs-spirit-stage-2"},
            ],
            "stage_3": [
                {"match_id": "300001", "teams": "Spirit vs 9z",
                 "url": "https://www.hltv.org/matches/300001/spirit-vs-9z-stage-3"},
                {"match_id": "300002", "teams": "Falcons vs G2",
                 "url": "https://www.hltv.org/matches/300002/falcons-vs-g2-stage-3"},
                {"match_id": "300003", "teams": "Natus Vincere vs Falcons",
                 "url": "https://www.hltv.org/matches/300003/navi-vs-falcons-stage-3"},
            ],
        },
    }
    (root / "data" / "intake-seeds" / "iem-cologne-major-2026-stage2-stage3-match-pages.json")\
        .write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

    # scripts/download_cologne_major_2026.py (truncated with PLAYOFFS)
    scripts_dir = root / "scripts"
    scripts_dir.mkdir()
    playoff_script = """
PLAYOFFS = [
    ("400001", "G2 vs Spirit", "https://www.hltv.org/matches/400001/g2-vs-spirit-playoffs"),
    ("400002", "FURIA vs Falcons", "https://www.hltv.org/matches/400002/furia-vs-falcons-playoffs"),
    ("400003", "Falcons vs Vitality", "https://www.hltv.org/matches/400003/falcons-vs-vitality-playoffs"),
]
"""
    (scripts_dir / "download_cologne_major_2026.py").write_text(playoff_script, encoding="utf-8")

    # reports/raw-corpus-inventory.json
    (root / "reports").mkdir()
    inv = {
        "total_archives": 7,
        "total_members": 13,
        "archives": [
            # Stage 2: Spirit vs 9z (200001)
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/stage-2/iem-cologne-major-2026-stage-2-spirit-vs-9z-bo3-abc.rar",
                "stage": "stage-2", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "spirit-vs-9z-m1-mirage.dem", "map": "de_mirage", "size_bytes": 1000,
                     "duplicate_key": "spirit-vs-9z-m1-mirage.dem::1000"},
                ],
            },
            # Stage 2: Astralis vs Spirit (200002)
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/stage-2/iem-cologne-major-2026-stage-2-astralis-vs-spirit-bo3-def.rar",
                "stage": "stage-2", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "astralis-vs-spirit-m1-nuke.dem", "map": "de_nuke", "size_bytes": 1001,
                     "duplicate_key": "astralis-vs-spirit-m1-nuke.dem::1001"},
                ],
            },
            # Stage 3: Spirit vs 9z (300001) — same teams, different stage
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/stage-3/iem-cologne-major-2026-spirit-vs-9z-bo3-ghi.rar",
                "stage": "stage-3", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "spirit-vs-9z-m1-dust2.dem", "map": "de_dust2", "size_bytes": 1002,
                     "duplicate_key": "spirit-vs-9z-m1-dust2.dem::1002"},
                ],
            },
            # Stage 3: Falcons vs G2 (300002)
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/stage-3/iem-cologne-major-2026-falcons-vs-g2-bo3-jkl.rar",
                "stage": "stage-3", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "falcons-vs-g2-m1-inferno.dem", "map": "de_inferno", "size_bytes": 1003,
                     "duplicate_key": "falcons-vs-g2-m1-inferno.dem::1003"},
                ],
            },
            # Stage 3: NAVI vs Falcons (300003)
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/stage-3/iem-cologne-major-2026-natus-vincere-vs-falcons-bo3-mno.rar",
                "stage": "stage-3", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "navi-vs-falcons-m1-ancient.dem", "map": "de_ancient", "size_bytes": 1004,
                     "duplicate_key": "navi-vs-falcons-m1-ancient.dem::1004"},
                ],
            },
            # Playoffs: G2 vs Spirit (400001)
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/playoffs/iem-cologne-major-2026-g2-vs-spirit-bo3-pqr.rar",
                "stage": "playoffs", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "g2-vs-spirit-m1-overpass.dem", "map": "de_overpass", "size_bytes": 1005,
                     "duplicate_key": "g2-vs-spirit-m1-overpass.dem::1005"},
                ],
            },
            # Playoffs: FURIA vs Falcons (400002) — single-map .dem as secondary
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/playoffs/iem-cologne-major-2026-furia-vs-falcons-bo5-stu.rar",
                "stage": "playoffs", "sub_stage": None,
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "furia-vs-falcons-m1-mirage.dem", "map": "de_mirage", "size_bytes": 1006,
                     "duplicate_key": "furia-vs-falcons-m1-mirage.dem::1006"},
                ],
            },
            # Playoffs: FURIA vs Falcons — single-map .dem extra copy → ambiguous candidate
            {
                "archive_path": "data/raw/events/iem-cologne-major-2026/playoffs/single-map-demos/furia-vs-falcons-m1-mirage.dem",
                "stage": "playoffs", "sub_stage": "single-map-demos",
                "event": "iem-cologne-major-2026",
                "members": [
                    {"member": "furia-vs-falcons-m1-mirage.dem", "map": "de_mirage", "size_bytes": 1006,
                     "duplicate_key": "furia-vs-falcons-m1-mirage.dem::1006"},
                ],
            },
        ],
    }
    (root / "reports" / "raw-corpus-inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False), encoding="utf-8"
    )

    return root


@pytest.fixture
def json_out(tmp_path: Path) -> Path:
    return tmp_path / "registry.json"


@pytest.fixture
def md_out(tmp_path: Path) -> Path:
    return tmp_path / "registry.md"


# ═════════════════════════════════════════════════════════════════════════
#   Tests
# ═════════════════════════════════════════════════════════════════════════


class TestCrossStage:
    """Same teams across different stages must not be confused."""

    def test_stage2_and_stage3_spirit_vs_9z(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Spirit vs 9z appears in Stage 2 (200001) and Stage 3 (300001) — distinct."""
        result = _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out),
            "--report", str(md_out),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        r = _read_json(json_out)
        recs = {rec["match_id"]: rec for rec in r["records"]}
        # Stage 2 Spirit vs 9z
        s2 = recs["200001"]
        assert s2["stage"] == "stage-2"
        assert s2["status"] == "registered"
        assert "stage-2" in s2["archive_path"]

        # Stage 3 Spirit vs 9z
        s3 = recs["300001"]
        assert s3["stage"] == "stage-3"
        assert s3["status"] == "registered"
        assert "stage-3" in s3["archive_path"]

        # They must have DIFFERENT archive paths
        assert s2["archive_path"] != s3["archive_path"]


class TestOneToOne:
    """Normal 1:1 binding."""

    def test_basic_registration(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Astralis vs Spirit → registered with correct members."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        rec = next(rec for rec in r["records"] if rec["match_id"] == "200002")
        assert rec["status"] == "registered"
        assert len(rec["members"]) == 1
        assert rec["members"][0]["map"] == "de_nuke"

    def test_member_data_preserved(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Member map name from inventory is preserved in registry."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        rec = next(rec for rec in r["records"] if rec["match_id"] == "300002")
        assert rec["status"] == "registered"
        maps = [m["map"] for m in rec["members"]]
        assert "de_inferno" in maps


class TestMissingArchive:
    """Matches with no corresponding archive on disk."""

    def test_missing_flagged(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """If no archive exists for a match → status=missing_archive."""
        # Add a seed match without a corresponding archive
        seed_file = fake_corpus / "data" / "intake-seeds" / "iem-cologne-major-2026-stage2-stage3-match-pages.json"
        seed = json.loads(seed_file.read_text(encoding="utf-8"))
        seed["stages"]["stage_3"].append({
            "match_id": "399999",
            "teams": "BetBoom vs B8",
            "url": "https://www.hltv.org/matches/399999/betboom-vs-b8",
        })
        seed_file.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        missing = [rec for rec in r["records"] if rec["status"] == "missing_archive"]
        missing_ids = [rec["match_id"] for rec in missing]
        assert "399999" in missing_ids
        assert r["summary"]["missing_archive"] >= 1


class TestAmbiguous:
    """Multiple archives matching one match ID."""

    def test_ambiguous_detected(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Two archives for FURIA vs Falcons → registered (primary chosen), extra noted."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        rec = next(rec for rec in r["records"] if rec["match_id"] == "400002")
        # Primary (BO5) is registered, single-map.dem is "extra_archives"
        assert rec["status"] == "registered"
        assert "extra_archives" in rec
        assert len(rec["extra_archives"]) == 1
        assert "single-map-demos" in rec["extra_archives"][0]


class TestCompleteness:
    """All match IDs must be covered."""

    def test_8_seeds_covered(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """8 seed matches → 8 records in output (plus playoffs)."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        # 2 (stage_2) + 3 (stage_3) + 3 (playoffs) = 8
        assert r["total_match_ids"] == 8
        assert len(r["records"]) == 8

    def test_all_stages_have_records(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Stage summary includes all three stages."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        for stage in ("playoffs", "stage-2", "stage-3"):
            assert stage in r["stage_summary"], f"missing stage {stage}"


class TestOutput:
    """Both JSON and Markdown output."""

    def test_markdown_generated(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Markdown report exists and contains key sections."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        assert md_out.is_file()
        md = md_out.read_text(encoding="utf-8")
        assert "注册表" in md
        assert "registered" in md.lower()
        assert "missing" in md.lower()

    def test_boundary_in_json(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """JSON contains boundary disclaimer."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        assert "boundary" in r
        assert not r["boundary"].startswith("基于")  # should be in Chinese


class TestTeamNormalization:
    """Edge cases in team name matching."""

    def test_case_sensitivity(self, fake_corpus: Path, json_out: Path, md_out: Path) -> None:
        """Mixed case team names → matched case-insensitively."""
        _run_script(fake_corpus,
            "--inventory", str(fake_corpus / "reports" / "raw-corpus-inventory.json"),
            "--output", str(json_out), "--report", str(md_out),
        )
        r = _read_json(json_out)
        # FURIA vs Falcons → should match "furia-vs-falcons" in filename
        rec = next(rec for rec in r["records"] if rec["match_id"] == "400002")
        assert rec["status"] == "registered"
