#!/usr/bin/env python3
"""Print a compact, human-readable status for the Cologne corpus download."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "reports" / "iem-cologne-major-2026-download-state.json"
RAW_ROOT = ROOT / "data" / "raw" / "iem-cologne-major-2026"
TOTAL_MATCHES = 73
ORIGINALLY_PRESENT = 7


def prop_count(value: object) -> int:
    return len(value) if isinstance(value, dict) else 0


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    completed = prop_count(state.get("completed"))
    errors = prop_count(state.get("errors"))
    full = list(RAW_ROOT.rglob("*.rar")) if RAW_ROOT.exists() else []
    partial = list(RAW_ROOT.rglob("*.rar.part")) if RAW_ROOT.exists() else []
    size_gb = sum(path.stat().st_size for path in full) / 1024**3
    print("IEM Cologne Major 2026 下载进度")
    print(f"新下载完成：{completed} 场")
    print(f"赛事总语料：约 {ORIGINALLY_PRESENT + completed}/{TOTAL_MATCHES} 场（含此前已有 7 场）")
    print(f"新下载体积：{size_gb:.2f} GB，完整归档 {len(full)} 个")
    print(f"正在传输：{len(partial)} 个 .part 文件")
    print(f"待重试记录：{errors} 场")
    print(f"状态更新时间：{state.get('updated_at', '尚未开始')}")
    print(f"文件位置：{RAW_ROOT}")


if __name__ == "__main__":
    main()
