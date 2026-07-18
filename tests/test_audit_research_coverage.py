from __future__ import annotations

from scripts.audit_research_coverage import build_report


def test_report_uses_read_only_coverage_rows(tmp_path):
    report = build_report(tmp_path / "series", tmp_path / "processed", 5)
    assert report["threshold_matches"] == 5
    assert report["complete_series"] == []
    assert report["unassigned_parsed_bundles"] == []
    assert "不修改数据" in str(report["boundary"])
