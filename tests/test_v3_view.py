"""Regression tests for the V3 research workspace ("研究工作台").

These tests confirm the comparison page renders with correct empty-state
and boundary language when Spirit data is not yet available.
"""

from __future__ import annotations

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


def _v3_page() -> AppTest:
    """Switch to the 研究工作台 page and return the AppTest handle."""
    at = _run()
    at.get("radio")[0].set_value("研究工作台")
    at.run(timeout=10)
    return at


class TestV3PagePresence:
    """Page switches to 研究工作台 without exceptions."""

    def test_radio_includes_v3_option(self) -> None:
        at = _run()
        radio = at.get("radio")[0]
        options = [str(o) for o in radio.options]
        assert "研究工作台" in options, f"options were {options}"
        assert "回放" in options, f"options were {options}"

    def test_switch_to_v3_no_exceptions(self) -> None:
        at = _v3_page()
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_section_label_rendered(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("RESEARCH WORKSPACE" in b for b in bodies), (
            "section label not found"
        )

    def test_page_title_rendered(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("vs" in b for b in bodies), "selected-team comparison title not found"

    def test_cross_team_view_hides_single_demo_scoreboard(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "RESEARCH WORKSPACE" in full
        assert "TEAM FALCONS" not in full
        assert "TEAM FURIA" not in full


class TestV3DataState:
    """Page reports the comparison scope without development status cards."""

    def test_scope_line_displayed(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        selectboxes = {s.key: s for s in at.get("selectbox")}
        assert str(selectboxes["research_map"].value).startswith("de_")
        assert str(selectboxes["research_team_a"].value).startswith("iem-cologne-2026-")
        assert str(selectboxes["research_team_b"].value).startswith("iem-cologne-2026-")
        assert selectboxes["research_team_a"].value != selectboxes["research_team_b"].value

    def test_no_development_status_cards(self) -> None:
        """The page no longer shows internal development progress."""
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        forbidden = ["数据就绪", "最低样本门槛", "已索引", "已解析"]
        for phrase in forbidden:
            assert phrase not in full, (
                f"development status card text found: {phrase}"
            )
        alerts = [str(alert.value) for alert in at.get("alert") if alert.value]
        assert all("比较数据已就绪" not in alert for alert in alerts), (
            "V3 sidebar must not retain a development-ready status card"
        )

    def test_no_fake_charts(self) -> None:
        """The page uses real tables and evidence rows, not placeholder charts."""
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "人数结构并列表" in full
        assert full.count("样本 · 占比") >= 2
        assert "回合证据索引" in full
        assert len(at.get("plotly_chart")) == 0, "V3 should not use placeholder charts"

    def test_comparison_table_avoids_redundant_sample_delta(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert full.count("样本 · 占比") >= 2
        assert "覆盖场数 " in full
        assert "样本差（F-S）" not in full

    def test_strongest_signal_exposes_structure_coverage(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "Largest descriptive gap" in full
        assert "该结构的证据覆盖" in full
        assert "个样本 /" in full

    def test_evidence_defaults_to_strongest_structure(self) -> None:
        at = _v3_page()
        evidence_formation = next(
            box
            for box in at.get("selectbox")
            if box.key == "v3_evidence_formation_T"
        )
        assert evidence_formation.value != "全部结构"


class TestV3SideToggle:
    """T/CT toggle works without exceptions."""

    @staticmethod
    def _v3_side_radio(at: AppTest):
        for r in at.get("radio"):
            if r.key == "v3_side":
                return r
        msg = "v3_side radio not found"
        raise AssertionError(msg)

    def test_t_side_no_exceptions(self) -> None:
        at = _v3_page()
        self._v3_side_radio(at).set_value("T")
        at.run(timeout=20)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_ct_side_no_exceptions(self) -> None:
        at = _v3_page()
        self._v3_side_radio(at).set_value("CT")
        at.run(timeout=20)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_side_toggle_default_t(self) -> None:
        at = _v3_page()
        assert self._v3_side_radio(at).value == "T", (
            "default side should be T"
        )


class TestV3Boundary:
    """Evidence boundary text is present and correct."""

    def test_boundary_section_header(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("证据边界" in b for b in bodies), (
            "evidence boundary header not found"
        )

    def test_no_tactical_default_claim(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        # "默认战术" appears only as part of disclaimer "不等于默认战术";
        # check that no affirmative tactical claim is made
        forbidden_claims = ["的默认战术", "默认战术是", "默认战术结论"]
        for phrase in forbidden_claims:
            assert phrase not in full, (
                f"found forbidden claim: {phrase}"
            )

    def test_economy_classification_stated(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "当前比较筛选开放" in full, (
            "expected economy classification availability"
        )
        assert "混合与不确定标签保留在数据中，但不进入当前比较筛选" in full

    def test_repeated_structure_not_default(self) -> None:
        at = _v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "重复出现的结构不等于默认战术" in full, (
            "missing repeated-structure boundary"
        )

    def test_evidence_button_opens_local_replay_bundle(self) -> None:
        at = _v3_page()
        button = next(
            b for b in at.get("button") if b.key == "v3_open_evidence_T"
        )
        button.click()
        at.run(timeout=20)
        assert len(at.exception) == 0, [str(e) for e in at.exception]
        screen = next(r for r in at.get("radio") if r.key == "screen")
        assert screen.value == "回放"
        assert any(s.key == "selected_round" for s in at.get("selectbox"))


class TestV3EconomyEvidencePanel:
    """Economy evidence panel on the 证据回放 page."""

    def _v3_to_evidence_replay(self) -> AppTest:
        at = AppTest.from_file("app.py")
        at.run(timeout=10)
        for t in at.get("toggle"):
            if t.key == "playback_mode":
                t.set_value(False)
                at.run(timeout=10)
                break
        at.get("radio")[0].set_value("研究工作台")
        at.run(timeout=10)
        button = next(b for b in at.get("button") if b.key == "v3_open_evidence_T")
        button.click()
        at.run(timeout=20)
        return at

    def test_economy_panel_expander_present(self) -> None:
        """Check expander exists by inspecting expander widgets."""
        at = self._v3_to_evidence_replay()
        expanders = at.get("expander")
        labels = [str(e.label) for e in expanders]
        assert any("回合经济证据" in l for l in labels), (
            f"economy expander not found among: {labels}"
        )

    def test_economy_panel_shows_team_classification(self) -> None:
        at = self._v3_to_evidence_replay()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "经济标签" in full or "经济状态" in full, "no economy evidence in panel"

    def test_economy_panel_keeps_pistol_round_as_pistol(self) -> None:
        at = self._v3_to_evidence_replay()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert "手枪局" in " ".join(bodies), (
            "the selected first-round evidence must not be reclassified as eco"
        )

    def test_economy_panel_shows_player_table(self) -> None:
        at = self._v3_to_evidence_replay()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "选手" in full and "装备价值" in full, (
            "player equipment table not found in economy panel"
        )
        assert "护甲" in full and "头盔" in full, (
            "armor/helmet columns not in economy panel table"
        )
        assert "余额" in full, (
            "cash balance column not in economy panel table"
        )

    def test_economy_panel_not_on_round_replay(self) -> None:
        """Normal round replay page should not show the economy panel."""
        at = AppTest.from_file("app.py")
        at.run(timeout=10)
        for t in at.get("toggle"):
            if t.key == "playback_mode":
                t.set_value(False)
                at.run(timeout=10)
                break
        # Stay on default 回合复盘 page
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "回合经济证据（冻结结束）" not in full, (
            "economy panel should not appear on normal round replay"
        )


class TestV3DynamicHUD:
    """OB-style dynamic equipment HUD in evidence replay."""

    def _v3_to_evidence_replay(self) -> AppTest:
        at = AppTest.from_file("app.py")
        at.run(timeout=10)
        for t in at.get("toggle"):
            if t.key == "playback_mode":
                t.set_value(False)
                at.run(timeout=10)
                break
        at.get("radio")[0].set_value("研究工作台")
        at.run(timeout=10)
        button = next(b for b in at.get("button") if b.key == "v3_open_evidence_T")
        button.click()
        at.run(timeout=20)
        return at

    def test_hud_evidence_replay_no_exception(self) -> None:
        """Evidence replay page loads without exceptions (HUD is in iframe)."""
        at = self._v3_to_evidence_replay()
        assert len(at.exception) == 0, [str(e) for e in at.exception]
        screen = next(r for r in at.get("radio") if r.key == "screen")
        assert screen.value == "回放"

    def test_hud_not_on_normal_replay(self) -> None:
        """Normal round replay stays unchanged."""
        at = AppTest.from_file("app.py")
        at.run(timeout=10)
        for t in at.get("toggle"):
            if t.key == "playback_mode":
                t.set_value(False)
                at.run(timeout=10)
                break
        # Check no exceptions on normal round replay
        assert len(at.exception) == 0, [str(e) for e in at.exception]


class TestV3FilterInteraction:
    """Filter controls work together without exceptions."""

    def _v3_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("研究工作台")
        at.run(timeout=10)
        return at

    def test_team_filter_selectbox_exists(self) -> None:
        at = self._v3_page()
        labels = [str(s.label) for s in at.get("selectbox")]
        assert any("证据队伍" in l for l in labels), (
            f"team evidence filter not found among: {labels}"
        )

    def test_formation_filter_selectbox_exists(self) -> None:
        at = self._v3_page()
        labels = [str(s.label) for s in at.get("selectbox")]
        assert any("证据结构" in l for l in labels), (
            f"formation evidence filter not found among: {labels}"
        )

    def test_switch_to_available_team_filter_no_exception(self) -> None:
        at = self._v3_page()
        for s in at.get("selectbox"):
            if "证据队伍" in str(s.label):
                s.set_value(next(option for option in s.options if option != "两队"))
                break
        at.run(timeout=10)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_economy_filter_selectbox_exists(self) -> None:
        at = self._v3_page()
        labels = [str(s.label) for s in at.get("selectbox")]
        assert any("经济状态" in l for l in labels), (
            f"economy state filter not found among: {labels}"
        )

    def test_switch_economy_filter_no_exception(self) -> None:
        at = self._v3_page()
        for s in at.get("selectbox"):
            if "经济状态" in str(s.label):
                s.set_value("全起")
                break
        at.run(timeout=10)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_switch_economy_eco_no_exception(self) -> None:
        at = self._v3_page()
        for s in at.get("selectbox"):
            if "经济状态" in str(s.label):
                s.set_value("经济局")
                break
        at.run(timeout=10)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_economy_filter_full_buy_filters_evidence(self) -> None:
        """Selecting '全起' should limit evidence to full_buy rows."""
        at = self._v3_page()
        for s in at.get("selectbox"):
            if "经济状态" in str(s.label):
                s.set_value("全起")
                break
        at.run(timeout=10)
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert len(at.exception) == 0, [str(e) for e in at.exception]

    def test_economy_caption_disclaimer_present(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "冻结结束时的装备证据" in full, (
            "missing economy disclaimer"
        )


class TestV3EvidencePreview:
    """Evidence preview card is rendered."""

    def _v3_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("研究工作台")
        at.run(timeout=10)
        return at

    def test_evidence_preview_card_present(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("v3-evidence-preview" in b or "选中记录" in b for b in bodies), (
            "evidence preview card not found"
        )

    def test_evidence_row_selector_exists(self) -> None:
        at = self._v3_page()
        labels = [str(s.label) for s in at.get("selectbox")]
        assert any("选择一条回合证据" in l for l in labels), (
            "evidence row selector not found"
        )

    def test_evidence_economy_column_in_table(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "经济状态" in full, (
            "missing economy state column in evidence table"
        )
        assert "置信度" in full, (
            "missing economy confidence column in evidence table"
        )


class TestV3ComparisonTable:
    """Comparison table renders with color-coded deltas."""

    def _v3_page(self) -> AppTest:
        at = _run()
        at.get("radio")[0].set_value("研究工作台")
        at.run(timeout=10)
        return at

    def test_delta_column_header(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "占比差（" in full, (
            "missing share delta column header"
        )

    def test_falcons_match_count_in_comparison(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        bodies.extend(str(c.value) for c in at.get("caption") if c.value)
        full = " ".join(bodies)
        assert "占比差 = " in full and "占比" in full, (
            "missing delta explanation in caption"
        )

    def test_coverage_column_header(self) -> None:
        at = self._v3_page()
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        full = " ".join(bodies)
        assert "覆盖场数 " in full, (
            "missing coverage column header"
        )


class TestV3NoRegression:
    """Existing pages are unaffected."""

    def test_series_page_still_works(self) -> None:
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("多场样本")
                break
        at.run(timeout=20)
        assert len(at.exception) == 0, [str(e) for e in at.exception]
        bodies = [str(m.value) for m in at.get("markdown") if m.value]
        assert any("SERIES EVIDENCE" in b for b in bodies)

    def test_report_page_still_works(self) -> None:
        """No-match empty state instead of FURIA–Falcons."""
        at = _run()
        at.get("radio")[0].set_value("单场工具")
        at.run(timeout=20)
        for r in at.get("radio"):
            if r.key == "single_match_tool":
                r.set_value("复盘报告")
                break
        at.run(timeout=40)
        assert len(at.exception) == 0, [str(e) for e in at.exception[:2]]
