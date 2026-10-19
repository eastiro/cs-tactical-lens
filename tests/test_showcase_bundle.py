"""Tests for the lightweight public showcase bundle.

These tests require the showcase bundle to already exist at
``data/showcase/furia-falcons-mirage``.  If it does not exist all tests
are skipped with a clear message.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from helpers import load_manual_bundle
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_DIR = PROJECT_ROOT / "data" / "showcase" / "furia-falcons-mirage"
SOURCE_DIR = (
    PROJECT_ROOT
    / "data" / "processed" / "iem-cologne-major-2026-corpus"
    / "2395002" / "de_mirage"
)

pytestmark = [
    pytest.mark.skipif(
        not SHOWCASE_DIR.is_dir(),
        reason=f"Showcase bundle not found at {SHOWCASE_DIR}. Run scripts/build_showcase_bundle.py first.",
    ),
]

#: Tests that compare the showcase against the *source* corpus bundle need the
#: full local corpus, which is git-ignored.  Mark them so a clean clone reports
#: a clear skip instead of an opaque FileNotFoundError.
requires_source_corpus = pytest.mark.skipif(
    not SOURCE_DIR.is_dir(),
    reason=(
        "需要本地完整语料（data/processed/iem-cologne-major-2026-corpus/2395002/de_mirage）。"
        "公开仓库只附带 data/showcase 轻量包。"
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────


def _showcase_metadata() -> dict:
    return json.loads((SHOWCASE_DIR / "metadata.json").read_text(encoding="utf-8"))


def _source_metadata() -> dict:
    return json.loads((SOURCE_DIR / "metadata.json").read_text(encoding="utf-8"))


# ═════════════════════════════════════════════════════════════════════
# R1: .csv.gz loading via load_normalized_bundle
# ═════════════════════════════════════════════════════════════════════


class TestGzipLoading:
    """Loader falls back to .csv.gz when plain .csv is absent."""

    def test_positions_csv_gz_exists(self) -> None:
        assert (SHOWCASE_DIR / "positions.csv.gz").is_file(), (
            "positions.csv.gz must exist"
        )
        assert not (SHOWCASE_DIR / "positions.csv").exists(), (
            "plain positions.csv must NOT exist (only .gz should)"
        )

    def test_load_normalized_bundle_reads_gz(self) -> None:
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        assert len(data.positions) > 0, "positions should load from .csv.gz"

    def test_plain_csv_preferred_over_gz(self) -> None:
        """When both .csv and .csv.gz exist, .csv is read."""
        import shutil
        import tempfile

        from src.awpy_adapter import load_normalized_bundle
        tmp = Path(tempfile.mkdtemp(prefix="csvtest_"))
        try:
            bundle = tmp / "bundle"
            shutil.copytree(str(SHOWCASE_DIR), str(bundle))
            # Write a minimal positions.csv (should be preferred over .csv.gz)
            pd.DataFrame({"round": [1], "player": ["test"], "team": ["A"], "side": ["T"],
                           "seconds": [1.0], "x": [0.0], "y": [0.0], "area": ["A1"],
                           "health": [100], "tick": [100]}).to_csv(
                bundle / "positions.csv", index=False
            )
            data = load_normalized_bundle(bundle)
            assert len(data.positions) == 1, "should read the small .csv, not .csv.gz"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════
# R2: Data integrity — rounds, teams, maps
# ═════════════════════════════════════════════════════════════════════


class TestDataIntegrity:
    """Showcase bundle matches source bundle's core data."""

    def test_21_rounds(self) -> None:
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        assert len(data.rounds) == 21, f"expected 21 rounds, got {len(data.rounds)}"

    @requires_source_corpus
    def test_teams_match(self) -> None:
        meta = _showcase_metadata()
        src_meta = _source_metadata()
        assert meta["team_a"] == src_meta["team_a"], (
            f"team_a mismatch: {meta['team_a']} vs {src_meta['team_a']}"
        )
        assert meta["team_b"] == src_meta["team_b"]

    def test_map_name(self) -> None:
        meta = _showcase_metadata()
        assert meta["map_name"] == "de_mirage"

    def test_final_score(self) -> None:
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        final = data.rounds.iloc[-1]
        score_a, score_b = int(final.team_a_score), int(final.team_b_score)
        assert (score_a, score_b) == (13, 8), f"expected 13-8, got {score_a}-{score_b}"


# ═════════════════════════════════════════════════════════════════════
# R3: Event table row counts match source
# ═════════════════════════════════════════════════════════════════════


class TestEventTableIntegrity:
    """Event tables fully copied without data loss."""

    TABLES = [
        ("rounds.csv", "rounds.csv"),
        ("kills.csv", "kills.csv"),
        ("grenades.csv", "grenades.csv"),
        ("damages.csv", "damages.csv"),
        ("bomb_events.csv", "bomb_events.csv"),
        ("economy_snapshots.csv", "economy_snapshots.csv"),
        ("loadout_events.csv", "loadout_events.csv"),
    ]

    @requires_source_corpus
    @pytest.mark.parametrize("showcase_name, source_name", TABLES)
    def test_row_count_matches_source(self, showcase_name: str, source_name: str) -> None:
        def _count(path: Path) -> int:
            with path.open(encoding="utf-8") as f:
                return sum(1 for _ in csv.DictReader(f))

        src_rows = _count(SOURCE_DIR / source_name)
        out_rows = _count(SHOWCASE_DIR / showcase_name)
        assert out_rows == src_rows, (
            f"{showcase_name}: expected {src_rows} rows, got {out_rows}"
        )

    def test_loadout_events_present(self) -> None:
        le_path = SHOWCASE_DIR / "loadout_events.csv"
        assert le_path.is_file()
        with le_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0, "loadout_events must have data"
        from src.loadout_timeline import loadout_payload_for_round
        data = pd.read_csv(le_path)
        payload = loadout_payload_for_round(data, 1)
        assert payload["available"], "HUD payload must be available"


# ═════════════════════════════════════════════════════════════════════
# R4: 8 Hz sampling rules
# ═════════════════════════════════════════════════════════════════════


class TestPositionSampling:
    """Positions are downsampled to 8 Hz with proper rules."""

    def test_positions_csv_gz_readable(self) -> None:
        with gzip.open(SHOWCASE_DIR / "positions.csv.gz", "rt", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0, "gzipped positions must be readable"

    @requires_source_corpus
    def test_positions_significantly_reduced(self) -> None:
        with gzip.open(SHOWCASE_DIR / "positions.csv.gz", "rt", encoding="utf-8") as f:
            out_rows = list(csv.DictReader(f))
        with SOURCE_DIR.joinpath("positions.csv").open(encoding="utf-8") as f:
            src_rows = list(csv.DictReader(f))
        ratio = len(src_rows) / max(len(out_rows), 1)
        assert ratio >= 5, (
            f"positions should be at least 5x compressed, got {ratio:.1f}x ({len(src_rows)} -> {len(out_rows)})"
        )

    @requires_source_corpus
    def test_every_round_player_has_first_and_last(self) -> None:
        """Each round+player must have the earliest and latest tick preserved."""
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        public_bounds = data.positions.groupby(["round", "player"])["tick"].agg(["min", "max"])
        source = pd.read_csv(SOURCE_DIR / "positions.csv", usecols=["round", "player", "tick"])
        source_bounds = source.groupby(["round", "player"])["tick"].agg(["min", "max"])
        pd.testing.assert_frame_equal(public_bounds.sort_index(), source_bounds.sort_index())

    def test_seconds_monotonic_per_player(self) -> None:
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        pos = data.positions.sort_values(["round", "player", "seconds"])
        for (rnd, player), grp in pos.groupby(["round", "player"]):
            secs = grp["seconds"].tolist()
            for i in range(1, len(secs)):
                assert secs[i] >= secs[i - 1], (
                    f"R{rnd} {player}: seconds decreased at index {i}: {secs[i-1]} -> {secs[i]}"
                )

    def test_typical_sample_interval(self) -> None:
        """Adjacent samples for the same player should typically be ~0.125s apart."""
        from src.awpy_adapter import load_normalized_bundle
        data = load_normalized_bundle(SHOWCASE_DIR)
        pos = data.positions.sort_values(["round", "player", "seconds"])
        gaps = []
        for (rnd, player), grp in pos.groupby(["round", "player"]):
            secs = grp["seconds"].tolist()
            for i in range(1, len(secs)):
                gap = secs[i] - secs[i - 1]
                if gap > 0.01:  # ignore tiny floating-point duplicates
                    gaps.append(gap)
        median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 99
        assert 0.1 <= median_gap <= 0.2, (
            f"median sample gap should be ~0.125s for 8 Hz, got {median_gap:.4f}s"
        )


# ═════════════════════════════════════════════════════════════════════
# R5: No sensitive paths
# ═════════════════════════════════════════════════════════════════════


class TestNoSensitivePaths:
    """Public showcase must not contain local absolute paths."""

    SENSITIVE = ["D:\\", "C:\\", "EASTIRO", "好玩的项目"]

    @pytest.mark.parametrize("pattern", SENSITIVE)
    def test_no_absolute_paths(self, pattern: str) -> None:
        for f in SHOWCASE_DIR.rglob("*"):
            if not f.is_file() or f.suffix == ".gz":
                continue
            content = f.read_text(encoding="utf-8", errors="ignore")
            assert pattern not in content, (
                f"{f.name}: contains sensitive pattern '{pattern}'"
            )

    def test_no_raw_archive_path(self) -> None:
        meta = _showcase_metadata()
        for k, v in meta.items():
            if isinstance(v, str) and ("archive" in k.lower() or v.startswith("D:")):
                pytest.fail(f"metadata contains archive path: {k}={v}")


# ═════════════════════════════════════════════════════════════════════
# R6: Total size ≤ 30 MB
# ═════════════════════════════════════════════════════════════════════


class TestShowcaseSize:
    """Showcase must be within size limits."""

    def test_total_size_under_30_mb(self) -> None:
        total = sum(f.stat().st_size for f in SHOWCASE_DIR.rglob("*") if f.is_file())
        total_mb = total / 1024 / 1024
        assert total_mb <= 30, f"Showcase is {total_mb:.2f} MB (limit: 30 MB)"

    def test_showcase_manifest_exists(self) -> None:
        manifest_path = SHOWCASE_DIR / "showcase_manifest.json"
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest.get("showcase") is True
        assert manifest.get("position_sampling_hz") == 8


# ═════════════════════════════════════════════════════════════════════
# R7: AppTest — Empty replay page shows showcase button
# ═════════════════════════════════════════════════════════════════════


class TestShowcaseButtonAppears:
    """The showcase button appears on the empty replay page."""

    def test_showcase_button_exists(self) -> None:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        at.run(timeout=30)
        # Navigate to replay
        at.get("radio")[0].set_value("回放")
        at.run(timeout=15)
        buttons = {b.key: b for b in at.get("button")}
        assert "load_showcase_replay" in buttons, (
            "Showcase button must exist on empty replay page"
        )

    def _showcase_button(self, at):
        """Find the showcase button by key."""
        return next(b for b in at.get("button") if b.key == "load_showcase_replay")

    def test_showcase_button_loads_replay(self) -> None:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        at.run(timeout=30)
        at.get("radio")[0].set_value("回放")
        at.run(timeout=15)
        # Click showcase button
        self._showcase_button(at).click()
        at.run(timeout=45)

        assert "selected_round" in at.session_state, (
            "selected_round must be set after loading showcase"
        )
        assert "manual_replay_bundle" in at.session_state, (
            "manual_replay_bundle must be set"
        )
        # Verify it's the showcase bundle path
        assert str(at.session_state["manual_replay_bundle"]).endswith("furia-falcons-mirage"), (
            "Should point to showcase bundle"
        )

    def test_change_match_clears_showcase(self) -> None:
        """After '更换比赛', the showcase button reappears."""
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        at.run(timeout=30)
        at.get("radio")[0].set_value("回放")
        at.run(timeout=15)
        # Load showcase
        self._showcase_button(at).click()
        at.run(timeout=45)
        # Click 更换比赛
        btn = next(b for b in at.get("button") if b.key == "change_replay_source")
        btn.click()
        at.run(timeout=15)
        at.run(timeout=15)  # second run after rerun

        assert "manual_replay_bundle" not in at.session_state, (
            "manual_replay_bundle cleared after 更换比赛"
        )
        # Showcase button should be back
        btns = {b.key: b for b in at.get("button")}
        assert "load_showcase_replay" in btns, (
            "Showcase button must reappear after 更换比赛"
        )


# ═════════════════════════════════════════════════════════════════════
# R8: Existing tests not broken
# ═════════════════════════════════════════════════════════════════════


class TestExistingBehavior:
    """Existing replay and catalog behavior unaffected."""

    def test_available_research_profiles_unaffected(self) -> None:
        """Showcase must not increase available_research_profiles count."""
        from src.research_catalog import discover_research_profiles
        profiles = discover_research_profiles(PROJECT_ROOT / "data" / "series")
        assert all("showcase" not in p.profile_id.casefold() for p in profiles)

    def test_manual_replay_still_works(self) -> None:
        """Local corpus manual replay should still function."""
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        at.run(timeout=30)
        # A public clone intentionally has no local corpus; skip only in that
        # documented state instead of swallowing arbitrary regressions.
        if not SOURCE_DIR.is_dir():
            pytest.skip("full local corpus is not part of the public clone")
        load_manual_bundle(at, timeout=30)
        assert "selected_round" in at.session_state
        assert len(at.exception) == 0, [str(e.value) for e in at.exception]
