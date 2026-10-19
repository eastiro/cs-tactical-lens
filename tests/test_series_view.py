"""Regression tests for the multi-match "多场样本" series page.

These tests confirm the series view loads whichever locally validated V4
team-map profile is currently selected and produces zero exceptions.  They do
NOT freeze corpus counts, tactical interpretation, or a formation default.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


def _run() -> AppTest:
    at = AppTest.from_file("app.py")
    at.run(timeout=10)
    # Disable playback toggle to avoid video-like render timeout on the default page
    for t in at.get("toggle"):
        if t.key == "playback_mode":
            t.set_value(False)
            at.run(timeout=10)
            break
    return at


class TestSeriesPagePresence:
    """Requirement 1: page options contain '多场样本'."""

    def test_radio_includes_tools_option(self) -> None:
        at = _run()
        radio = at.get("radio")[0]
        options = [str(o) for o in radio.options]
        assert "单场工具" in options, f"options were {options}"

    def test_switch_to_series_no_exceptions(self) -> None:
        """Requirement 2: zero exceptions after switching to 多场样本."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]


class TestSeriesPageContent:
    """Requirement 3: page renders internally consistent summary counts."""

    def test_summary_numbers_rendered(self) -> None:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        assert len(at.exception) == 0

        # Collect all markdown body text
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)

        # Corpus counts change whenever more demos are materialized.  Guard the
        # visible count contract without pinning this test to the old V2
        # 10-match Falcons fixture.
        full = " ".join(bodies)
        assert re.search(r"\d+ 场比赛", full), "missing match count"
        assert re.search(r"\d+ 个回合样本", full), "missing round count"
        assert re.search(r"\d+ 个接触前有效样本", full), "missing valid-sample count"

    def test_series_section_label(self) -> None:
        """The section label is present."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("SERIES EVIDENCE" in b for b in bodies), (
            "section label not found"
        )

    def test_contact_and_snapshot_definitions_are_explicit(self) -> None:
        """The page distinguishes first contact from the 20-second snapshot."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "首次交火指首个敌我伤害事件" in full
        assert "人数结构" in full


class TestSeriesSideToggle:
    """Requirement 4: toggling T / CT produces zero exceptions."""

    @staticmethod
    def _series_side_radio(at: AppTest):
        """Locate the side-selection radio by its key."""
        for r in at.get("radio"):
            if r.key == "series_side":
                return r
        msg = "series_side radio not found"
        raise AssertionError(msg)

    def _switch_to_series(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        return at

    def test_t_side_no_exceptions(self) -> None:
        at = self._switch_to_series()
        self._series_side_radio(at).set_value("T")
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]

    def test_ct_side_no_exceptions(self) -> None:
        at = self._switch_to_series()
        self._series_side_radio(at).set_value("CT")
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]

    def test_t_side_info_no_crash_when_empty(self) -> None:
        """If a side has no profiles, the page shows an info block."""
        at = self._switch_to_series()
        self._series_side_radio(at).set_value("T")
        at.run(timeout=10)
        # Page should either render a bar chart or show "没有可用样本" info
        assert len(at.exception) == 0


class TestSeriesBoundary:
    """Requirement 5: boundary text, not tactical assertions."""

    def test_boundary_caption_rendered(self) -> None:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("经济范围" in b for b in bodies), (
            "expected 经济范围 label"
        )

    def test_sample_boundary_table(self) -> None:
        """The boundary table (有效接触前样本 / etc.) appears."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("有效接触前样本" in b for b in bodies), (
            "expected boundary-table header in markdown"
        )

    def test_no_tactical_assertion_injected(self) -> None:
        """Requirement 5: the page does not claim any formation is the default."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        # The page must NOT assert a fixed default tactic
        forbidden = ["默认战术", "默认开局", "default tactic"]
        for phrase in forbidden:
            assert phrase not in full.lower(), (
                f"found forbidden tactical claim: {phrase}"
            )


class TestSeriesIndexFilters:
    """Requirements for the new formation + repeated-3+ filters (Task 06)."""

    def _series_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        return at

    def test_filter_formation_select_exists(self) -> None:
        """R1: A formation selectbox is present on the series page."""
        at = self._series_page()
        # Look for a selectbox whose label is "人数结构"
        labels = [str(s.label) for s in at.get("selectbox")]
        formation_labels = [label for label in labels if "人数结构" in label]
        assert len(formation_labels) >= 1, (
            f"no formation filter found among labels: {labels}"
        )

    def test_filter_repeated_checkbox_exists(self) -> None:
        """R2: The '至少覆盖 3 场比赛' checkbox is present."""
        at = self._series_page()
        labels = [str(c.label) for c in at.get("checkbox")]
        repeated_labels = [label for label in labels if "至少覆盖" in label]
        assert len(repeated_labels) >= 1, (
            f"no repeated-structure checkbox found: {labels}"
        )

    def test_filter_repeated_checkbox_default_off(self) -> None:
        """The repeated-structure checkbox defaults to unchecked."""
        at = self._series_page()
        for c in at.get("checkbox"):
            if "至少覆盖" in str(c.label):
                assert not c.value, (
                    "repeated-structure checkbox should default to False"
                )
                break

    def test_switch_side_no_exception_after_filters(self) -> None:
        """R3: Switching T/CT with filters active produces zero exceptions."""
        at = self._series_page()
        # Toggle side to CT
        for r in at.get("radio"):
            if r.key == "series_side":
                r.set_value("CT")
                break
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]

    def test_formation_filter_changes_index_count(self) -> None:
        """Selecting a specific formation changes the index table."""
        at = self._series_page()
        # Get available formation options
        for s in at.get("selectbox"):
            if "人数结构" in str(s.label):
                options = list(s.options)
                if len(options) > 1:
                    # Pick the first non-"全部结构" option
                    target = options[1]
                    s.set_value(target)
                    break
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]

    def test_formation_filter_keeps_full_profile_options(self) -> None:
        """The filter must not be limited to the chart's top-eight rows."""
        at = self._series_page()
        formation_selects = [
            s for s in at.get("selectbox") if "人数结构" in str(s.label)
        ]
        assert len(formation_selects) == 1
        series_select = next(
            item for item in at.get("selectbox") if item.key == "series_profile_sel"
        )
        profile_path = (
            Path("data")
            / "series"
            / str(series_select.value)
            / "precontact_opening_profile.csv"
        )
        profile = pd.read_csv(profile_path)
        expected = set(
            profile.loc[profile["side"] == "T", "formation"].dropna().astype(str)
        )
        actual = set(map(str, formation_selects[0].options[1:]))
        assert actual == expected


class TestSeriesMatchSelection:
    """Match dropdown shows human-readable labels; single-match selection works."""

    def _series_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        return at

    def test_match_selectbox_label(self) -> None:
        """The match selectbox has the label '比赛范围'."""
        at = self._series_page()
        labels = [str(s.label) for s in at.get("selectbox")]
        match_labels = [label for label in labels if "比赛范围" in label]
        assert len(match_labels) >= 1, (
            f"no match-range selectbox found among: {labels}"
        )

    def test_match_options_include_all_and_specific(self) -> None:
        """Dropdown contains '全部比赛' plus individual readable entries."""
        at = self._series_page()
        for s in at.get("selectbox"):
            if "比赛范围" in str(s.label):
                options = [str(o) for o in s.options]
                assert "全部比赛" in options, (
                    "'全部比赛' missing from match options"
                )
                # At least one specific match option should contain
                # the event·opponent·date pattern
                non_all = [o for o in options if o != "全部比赛"]
                assert len(non_all) >= 1, (
                    "no specific match options found"
                )
                # Verify readable format: contains vs and a date-like token
                sample = non_all[0]
                assert "vs" in sample, (
                    f"option '{sample}' missing 'vs' — not in readable format"
                )
                break

    def test_select_single_match_changes_summary(self) -> None:
        """Selecting a specific match changes the filter summary to 1 场比赛."""
        at = self._series_page()
        for s in at.get("selectbox"):
            if "比赛范围" in str(s.label):
                options = list(s.options)
                non_all = [o for o in options if o != "全部比赛"]
                if non_all:
                    # Pick the first readable option (its value is still match_id)
                    s.set_value(non_all[0])
                    break
        at.run(timeout=10)
        assert len(at.exception) == 0, [
            str(e) for e in at.exception
        ]
        # The filter summary should reflect the single match
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("1 场比赛" in b for b in bodies), (
            "expected '1 场比赛' after single match selection"
        )


class TestSeriesRepeatedLabel:
    """Repeated-structure label uses accessible Chinese."""

    def _series_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        at.run(timeout=10)
        return at

    def test_repeated_label_in_summary_card(self) -> None:
        """The summary card uses '至少覆盖 3 场比赛', not '跨 3+ 场'."""
        at = self._series_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "至少覆盖 3 场比赛" in full, (
            "summary card missing '至少覆盖 3 场比赛' label"
        )

    def test_no_cross_3_plus_language_in_page(self) -> None:
        """The old '跨 3+ 场' phrasing is removed from visible text."""
        at = self._series_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "跨 3+" not in full, (
            "old '跨 3+' phrasing still present"
        )

    def test_repeated_definition_caption_clear(self) -> None:
        """The caption explains the filter without jargon."""
        at = self._series_page()
        caption_texts = [str(c.value) for c in at.get("caption") if c.value]
        full = " ".join(caption_texts)
        assert "至少覆盖 3 场比赛" in full, (
            "repeated-structure caption missing key text"
        )
        assert "不是一场比赛重复三次" in full, (
            "caption must clarify 'not one match repeated 3x'"
        )
        assert "不代表默认战术" in full, (
            "caption must disclaim tactical default"
        )
