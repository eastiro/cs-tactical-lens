"""pytest configuration with session-scoped AppTest for match data."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest


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
