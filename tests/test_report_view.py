"""Regression tests for the "复盘报告" auto-debrief page.

These tests confirm the debrief page renders with correct boundary
language and does not assert unsupported tactical conclusions.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

import pytest

from helpers import with_report


def _run() -> AppTest:
    at = AppTest.from_file("app.py")
    at.run(timeout=10)
    for t in at.get("toggle"):
        if t.key == "playback_mode":
            t.set_value(False)
            at.run(timeout=10)
            break
    return at


class TestReportPagePresence:
    """Page switches to 复盘报告 without exceptions."""

    def test_switch_to_report_no_exceptions(self) -> None:
        at = _run()
        with_report(at, load_data=False)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_section_label_rendered(self) -> None:
        at = _run()
        with_report(at, load_data=False)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        # When no match is loaded, the page shows the SINGLE-MATCH TOOLS label
        assert any("SINGLE-MATCH TOOLS" in b for b in bodies), (
            "section label not found"
        )

    def test_team_selector_present(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        labels = [str(s.label) for s in at.get("selectbox")]
        assert any("复盘对象" in l for l in labels), (
            "team selector not found"
        )


class TestReportBoundary:
    """Boundary card uses accurate V2 language, not '不在 V1'."""

    def test_no_old_v1_language(self) -> None:
        at = _run()
        with_report(at, load_data=False)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "不在 V1" not in full, (
            "still uses old '不在 V1' phrasing"
        )

    def test_uses_current_version_phrasing(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "本页不提供" in full, (
            f"missing '本页不提供' in boundary card:\n{full}"
        )

    def test_existing_boundary_kept(self) -> None:
        """The existing '既定战术需要多场样本' boundary is preserved."""
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "既定战术" in full, (
            "existing tactic boundary text removed"
        )
        assert "多场比赛" in full or "同队同图" in full, (
            "multi-match reference removed from boundary"
        )


class TestReportPageDivision:
    """Page division explanation distinguishes the three layers."""

    def test_single_match_summary_labeled(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "客观摘要" in full, (
            "missing single-match summary description"
        )

    def test_series_samples_labeled(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "多场样本" in full, (
            "missing series reference in page division"
        )

    def test_mid_round_snapshot_disclaimed(self) -> None:
        """Mid-round position is a snapshot, not team intent."""
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "不是队伍意图" in full, (
            "missing 'not team intent' disclaimer for mid-round snapshot"
        )


class TestReportNoUnsupportedConclusions:
    """Page must not assert unsupported tactical conclusions."""

    def test_no_default_tactic_claim(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        forbidden = ["默认战术", "default tactic", "战队习惯已确定"]
        for phrase in forbidden:
            assert phrase not in full, (
                f"found forbidden tactical claim: {phrase}"
            )

    def test_snapshot_not_tactical_intent(self) -> None:
        """Mid-round 5s caption must say 状态快照 or equivalent."""
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(c.value) for c in at.get("caption") if c.value]
        full = " ".join(bodies)
        assert any(phrase in full for phrase in [
            "状态快照", "不是战术意图", "不是战术意图判断"
        ]), "mid-round caption missing status-snapshot disclaimer"


class TestReportContentRenders:
    """Core content sections render with real match data."""

    def test_summary_header_rendered(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("本场客观摘要" in b for b in bodies), (
            "summary header not found"
        )

    def test_first_kill_table_rendered(self) -> None:
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("首杀证据表" in b for b in bodies), (
            "first-kill evidence table missing"
        )

    def test_metric_cards_rendered(self) -> None:
        """At least one metric card (st.metric) is visible."""
        at = _run()
        with_report(at, load_data=True)
        metrics = at.get("metric")
        assert len(metrics) >= 1, (
            "expected at least 1 metric card with real data"
        )

    def test_contact_index_or_info_rendered(self) -> None:
        """Either the contact index table or an info block is shown."""
        at = _run()
        with_report(at, load_data=True)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        has_index = any("交火证据索引" in b for b in bodies)
        has_info = any("证据不足" in b or "没有足够" in b for b in (
            str(i.value) for i in at.get("info")
        ))
        assert has_index or has_info, (
            "neither contact index nor empty-state info found"
        )
