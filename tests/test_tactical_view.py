"""Regression tests for the tactical page's evidence hierarchy."""

from __future__ import annotations

import pytest
from conftest import requires_local_corpus
from helpers import load_manual_bundle
from streamlit.testing.v1 import AppTest

# The Mirage tactical page needs a real Mirage bundle from the local corpus.
pytestmark = requires_local_corpus


def _tactical_page() -> AppTest:
    at = AppTest.from_file("app.py").run(timeout=30)
    # Tactical area grouping is deliberately Mirage-specific.  V4 contains
    # many maps, so never depend on the alphabetically first profile here.
    load_manual_bundle(
        at,
        timeout=30,
        profile_id="iem-cologne-2026-falcons-de_mirage",
    )
    at.get("radio")[0].set_value("单场工具")
    at.run(timeout=30)
    for r in at.get("radio"):
        if r.key == "single_match_tool":
            r.set_value("战术模式")
            break
    at.run(timeout=30)
    return at


def test_opening_structure_is_the_primary_tactical_section() -> None:
    at = _tactical_page()
    assert len(at.exception) == 0, [str(e) for e in at.exception[:2]]
    bodies = [str(m.value) for m in at.get("markdown") if m.value]
    assert any("接触前开局结构" in body for body in bodies)


def test_position_snapshot_is_explicitly_secondary() -> None:
    at = _tactical_page()
    assert len(at.exception) == 0, [str(e) for e in at.exception[:2]]
    expanders = [str(item.label) for item in at.get("expander")]
    assert any("辅助视图：多回合位置观测" in label for label in expanders)
