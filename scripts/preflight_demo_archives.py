r"""Preflight check for newly downloaded CS2 demo archives.

Before importing a fresh BO3/BO5 archive into the pipeline, run this script to
see which maps are present, spot potential duplicates, and get a clear list of
what can be passed to :doc:`import_match_archives.py`.

Usage::

    python scripts/preflight_demo_archives.py data/raw/new-batch
        --output reports/new-batch-preflight.json

The script never extracts, parses, or moves any file — it only reads filenames
and archive tables-of-contents.

"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


# Reuse map-name helpers from the sibling catalog script.
# Keep the import minimal so refactoring catalog_match_archives doesn't
# silently change this script's behaviour.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_match_archives import (  # noqa: E402  # isort:skip
    ARCHIVE_SUFFIXES,
    MAP_NAMES,
    _find_7z,
    _map_name,
    _match_slug,
)

DEMO_SUFFIX = ".dem"
NON_7Z_SUFFIXES = {".rar", ".7z"}
_7Z_NEEDED_MESSAGE = "无法枚举，需要 7-Zip"
_ENUMERATE_ERROR = "enumeration_error"


def _archive_members(
    path: Path, seven_zip: str | None,
) -> tuple[list[tuple[str, int]], str | None, str | None]:
    """Enumerate ``.dem`` members inside *path*.

    Returns
        (members, status, error_message)
        where ``status`` is ``"ok"``, ``"needs_7zip"``, or ``"enumeration_error"``.
    """
    suffix = path.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                members = [
                    (member.filename, member.file_size)
                    for member in archive.infolist()
                    if member.filename.lower().endswith(DEMO_SUFFIX)
                ]
            return members, "ok", None
        except (zipfile.BadZipFile, OSError) as exc:
            return [], _ENUMERATE_ERROR, str(exc)

    if not seven_zip:
        return [], "needs_7zip", _7Z_NEEDED_MESSAGE

    try:
        result = subprocess.run(
            [seven_zip, "l", "-slt", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode:
            return [], _ENUMERATE_ERROR, result.stderr.strip() or result.stdout.strip()
    except OSError as exc:
        return [], _ENUMERATE_ERROR, str(exc)

    members: list[tuple[str, int]] = []
    record: dict[str, str] = {}
    for line in [*result.stdout.splitlines(), ""]:
        if not line.strip():
            member = record.get("Path", "")
            if member.lower().endswith(DEMO_SUFFIX):
                members.append((member, int(record.get("Size", "0"))))
            record = {}
        elif " = " in line:
            key, value = line.split(" = ", 1)
            record[key] = value
    return members, "ok", None


def _preflight_one(
    source: Path, seven_zip: str | None,
) -> dict[str, object]:
    """Run preflight on a single file (``.dem`` or archive)."""
    suffix = source.suffix.lower()
    if suffix == DEMO_SUFFIX:
        size = source.stat().st_size
        member_name = source.name
        return {
            "archive_path": str(source.resolve()),
            "archive_suffix": suffix,
            "archive_size_bytes": size,
            "enumerate_status": "ok",
            "error_message": None,
            "members": [
                {
                    "member": member_name,
                    "map": _map_name(member_name),
                    "size_bytes": size,
                    "match_slug": _match_slug(source),
                    "duplicate_key": f"{Path(member_name).name.lower()}::{size}",
                }
            ],
        }

    if suffix in ARCHIVE_SUFFIXES:
        members, status, error = _archive_members(source, seven_zip)
        return {
            "archive_path": str(source.resolve()),
            "archive_suffix": suffix,
            "archive_size_bytes": source.stat().st_size,
            "enumerate_status": status,
            "error_message": error,
            "members": [
                {
                    "member": member_name,
                    "map": _map_name(member_name),
                    "size_bytes": dem_size,
                    "match_slug": _match_slug(source),
                    "duplicate_key": f"{Path(member_name).name.lower()}::{dem_size}",
                }
                for member_name, dem_size in members
            ],
        }

    return None


def _build_summary(archives: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate per-map counts and duplicate candidates across all archives."""
    all_members: list[dict[str, object]] = []
    for archive in archives:
        all_members.extend(archive["members"])  # type: ignore[arg-type]

    map_counts: dict[str, int] = {}
    unknown = 0
    for member in all_members:
        m = str(member["map"])
        map_counts[m] = map_counts.get(m, 0) + 1
        if m == "unknown":
            unknown += 1

    # Detect duplicate candidates across archives: same duplicate_key appears
    # in multiple members.
    key_counts: dict[str, int] = {}
    for member in all_members:
        k = str(member["duplicate_key"])
        key_counts[k] = key_counts.get(k, 0) + 1
    duplicate_candidates = sum(1 for c in key_counts.values() if c > 1)

    archives_needing_7zip = sum(
        1 for a in archives if a.get("enumerate_status") == "needs_7zip"
    )
    archives_with_errors = sum(
        1 for a in archives if a.get("enumerate_status") == _ENUMERATE_ERROR
    )

    return {
        "total_archives": len(archives),
        "total_members": len(all_members),
        "archives_with_errors": archives_with_errors,
        "archives_needing_7zip": archives_needing_7zip,
        "maps": dict(sorted(map_counts.items())),
        "unknown_map_count": unknown,
        "duplicate_candidate_count": duplicate_candidates,
        "boundary": "仅基于文件名/归档目录预检，不能证明队伍、阵容期或解析成功。"
        "实际导入时会再次校验队伍、地图和阵容。",
    }


def _canonicalize(archives: list[dict[str, object]]) -> list[dict[str, object]]:
    """Sort archives and their members for deterministic output."""
    archives.sort(key=lambda a: str(a.get("archive_path", "")))
    for archive in archives:
        members = archive.get("members", [])
        if isinstance(members, list):
            members.sort(key=lambda m: str(m.get("member", "")))
    return archives


def main() -> None:
    parser = argparse.ArgumentParser(
        description="下载后、导入前的 Demo archive 预检——"
        "列出地图、识别重复风险、生成导入清单"
    )
    parser.add_argument(
        "source", type=Path,
        help="存放 .dem / .zip / .rar / .7z 的目录（会递归扫描）",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="JSON 报告输出路径（父目录不存在会自动创建）",
    )
    args = parser.parse_args()

    if not args.source.is_dir():
        parser.error(f"找不到目录：{args.source}")

    seven_zip = _find_7z()

    archives: list[dict[str, object]] = []
    for entry in sorted(args.source.rglob("*")):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix == DEMO_SUFFIX or suffix in ARCHIVE_SUFFIXES:
            result = _preflight_one(entry, seven_zip)
            if result is not None:
                archives.append(result)

    if not archives:
        print("未找到 .dem、.zip、.rar 或 .7z 文件。")
        sys.exit(1)

    archives = _canonicalize(archives)
    summary = _build_summary(archives)

    report = {
        "preflight_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(args.source.resolve()),
        "archives": archives,
        "summary": summary,
    }

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"预检完成：{output}")
    print(f"共 {summary['total_archives']} 个来源 · "
          f"{summary['total_members']} 张 Demo · "
          f"{summary['unknown_map_count']} 未知地图 · "
          f"{summary['duplicate_candidate_count']} 重复候选")


if __name__ == "__main__":
    main()
