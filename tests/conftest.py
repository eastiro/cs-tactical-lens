"""Shared pytest configuration and local-corpus availability guards.

The public repository ships a lightweight *showcase* bundle under
``data/showcase/``.  The full 135-demo corpus under ``data/processed/`` is
deliberately git-ignored because it is large and licensed third-party content,
so a fresh clone legitimately has neither.  Tests that need the full corpus
must skip with an explicit reason instead of failing with a bare
``FileNotFoundError``, which previously made a clean checkout look broken.

Import the guards below rather than re-deriving paths per module so the
definition of "usable bundle" stays in one place.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
#: Bundle the app opens by default for 单场工具 / 战术模式 / 复盘报告.
DEFAULT_BUNDLE = PROJECT_ROOT / "data" / "processed" / "furia-falcons-mirage"
#: First-party showcase bundle that is safe to commit.
SHOWCASE_BUNDLE = PROJECT_ROOT / "data" / "showcase" / "furia-falcons-mirage"
CORPUS_ROOT = PROJECT_ROOT / "data" / "processed" / "iem-cologne-major-2026-corpus"
SERIES_ROOT = PROJECT_ROOT / "data" / "series"

#: Files a bundle must contain before :func:`src.awpy_adapter.load_normalized_bundle`
#: can succeed.  ``positions`` may be stored either raw or gzip-compressed.
REQUIRED_BUNDLE_FILES = ("metadata.json", "rounds.csv", "kills.csv")
POSITION_CANDIDATES = ("positions.csv", "positions.csv.gz")

LOCAL_CORPUS_SKIP_REASON = (
    "需要本地完整语料（data/processed/furia-falcons-mirage 含 positions.csv）。"
    "公开仓库只附带 data/showcase 轻量包，重建方式见 data/showcase/README.md。"
)


def bundle_is_usable(bundle_dir: Path) -> bool:
    """Return True when *bundle_dir* holds every file the loader requires."""
    if not all((bundle_dir / name).is_file() for name in REQUIRED_BUNDLE_FILES):
        return False
    return any((bundle_dir / name).is_file() for name in POSITION_CANDIDATES)


#: ``True`` when the default processed bundle can actually be loaded.
DEFAULT_BUNDLE_AVAILABLE = bundle_is_usable(DEFAULT_BUNDLE)

requires_default_bundle = pytest.mark.skipif(
    not DEFAULT_BUNDLE_AVAILABLE,
    reason=LOCAL_CORPUS_SKIP_REASON,
)


def _discoverable_profiles(root: Path) -> int:
    """Count series profiles whose ``manifest.json`` points at loadable bundles.

    A profile manifest is ``<profile-id>.json`` at ``data/series/`` and lists
    match entries with ``bundle`` paths resolved against the series directory.
    """
    if not root.is_dir():
        return 0
    count = 0
    for manifest_path in root.glob("*.json"):
        if manifest_path.name.endswith(".example.json"):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for match in manifest.get("matches", []) or []:
            bundle = str(match.get("bundle", "")).strip()
            if not bundle:
                continue
            candidate = Path(bundle)
            if not candidate.is_absolute():
                candidate = (manifest_path.parent / candidate).resolve()
            if bundle_is_usable(candidate):
                count += 1
                break
    return count


#: The 单场工具 / 战术模式 / 复盘报告 pages drive ``load_manual_bundle``, which
#: needs at least one profile whose bundle is actually present on disk.
LOCAL_CORPUS_AVAILABLE = (
    DEFAULT_BUNDLE_AVAILABLE
    or bundle_is_usable(CORPUS_ROOT / "2395002" / "de_mirage")
    or _discoverable_profiles(SERIES_ROOT) > 0
)

requires_local_corpus = pytest.mark.skipif(
    not LOCAL_CORPUS_AVAILABLE,
    reason=(
        "需要本地完整语料（data/processed 或 data/series 中存在可加载的比赛 bundle）。"
        "公开仓库只附带 data/showcase 轻量包；回放以外的工具页需要一个真实比赛，"
        "重建方式见 data/showcase/README.md。"
    ),
)


@pytest.fixture(scope="session")
def loaded_app() -> AppTest:
    """Create an AppTest and load one match via the 回放 profile selector.

    This fixture is session-scoped so tests share the same loaded AppTest
    without each re-navigating through the UI.
    """
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    for t in at.get("toggle"):
        if t.key == "playback_mode":
            t.set_value(False)
            at.run(timeout=15)
            break
    # Navigate to 回放 and use profile→match selector
    at.get("radio")[0].set_value("回放")
    at.run(timeout=15)
    # First render: profile selector appears with default
    at.run(timeout=15)
    # Now match list renders
    for s in at.get("selectbox"):
        if s.key == "replay_match_sel":
            break
    for b in at.get("button"):
        if b.key == "load_manual_replay":
            b.click()
            at.run(timeout=30)
            break
    return at
