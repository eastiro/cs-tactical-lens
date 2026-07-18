"""Shared AppTest helpers for V3.3 navigation through the visible UI."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def load_manual_bundle(
    at: AppTest,
    *,
    timeout: int = 30,
    profile_id: str | None = None,
) -> AppTest:
    """Use the same profile → match → load path exposed to a user."""
    if profile_id is not None:
        at.session_state["replay_profile_sel"] = profile_id
    at.get("radio")[0].set_value("回放")
    at.run(timeout=timeout)
    # The initial selectbox value is already the first valid profile id.
    # AppTest exposes formatted display text in ``options``, so re-setting it
    # would corrupt the widget state instead of simulating a user choice.
    next(item for item in at.get("selectbox") if item.key == "replay_profile_sel")
    load = next(item for item in at.get("button") if item.key == "load_manual_replay")
    load.click()
    at.run(timeout=timeout)
    return at


def with_report(at: AppTest, *, load_data: bool = False, timeout: int = 15) -> AppTest:
    """Navigate to 单场工具 → 复盘报告, optionally injecting match data."""
    if load_data:
        load_manual_bundle(at, timeout=timeout)
    at.get("radio")[0].set_value("单场工具")
    at.run(timeout=timeout)
    _set_radio(at, "single_match_tool", "复盘报告", timeout)
    return at


def with_tactical(at: AppTest, *, load_data: bool = False, timeout: int = 15) -> AppTest:
    """Navigate to 单场工具 → 战术模式, optionally injecting match data."""
    if load_data:
        load_manual_bundle(at, timeout=timeout)
    at.get("radio")[0].set_value("单场工具")
    at.run(timeout=timeout)
    _set_radio(at, "single_match_tool", "战术模式", timeout)
    return at


def with_series(at: AppTest, *, timeout: int = 15) -> AppTest:
    """Navigate to 单场工具 → 多场样本."""
    at.get("radio")[0].set_value("单场工具")
    at.run(timeout=timeout)
    _set_radio(at, "single_match_tool", "多场样本", timeout)
    return at


def _set_radio(at: AppTest, key: str, value: str, timeout: int) -> None:
    for r in at.get("radio"):
        if r.key == key:
            r.set_value(value)
            at.run(timeout=timeout)
            return
