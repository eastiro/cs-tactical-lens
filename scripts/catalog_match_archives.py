r"""Build a non-destructive map catalog from downloaded CS2 match archives.

The raw directory remains the source of truth: a BO3/BO5 archive is never
renamed, moved, extracted, or duplicated.  This script only records which
``.dem`` files it contains, so later imports can target any team/map without
downloading the same match again.

Example:
    python scripts\\catalog_match_archives.py data\\raw\\falcons-mirage \\
        --team "Team Falcons" --target-map de_mirage \
        --output data\catalog\team-falcons\2026-karrigan
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ARCHIVE_SUFFIXES = {".rar", ".7z", ".zip"}
MAP_NAMES = {
    "ancient", "anubis", "cache", "cobblestone", "dust2", "inferno",
    "mirage", "nuke", "overpass", "train", "vertigo",
}


def _find_7z() -> str | None:
    """Locate 7-Zip, including the bundled executable on this Windows setup."""
    candidates = [
        shutil.which("7z"),
        shutil.which("7za"),
        r"C:\\Program Files\\7-Zip\\7z.exe",
        r"C:\\Program Files (x86)\\7-Zip\\7z.exe",
        r"C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\7z.exe",
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def _archive_members(path: Path, seven_zip: str | None) -> list[tuple[str, int]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return [
                (member.filename, member.file_size)
                for member in archive.infolist()
                if member.filename.lower().endswith(".dem")
            ]
    if not seven_zip:
        raise RuntimeError(
            f"无法读取 {path.name}：未找到 7-Zip。请安装 7-Zip，或把 .rar 先解压成目录。"
        )
    result = subprocess.run(
        [seven_zip, "l", "-slt", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode:
        raise RuntimeError(f"无法读取 {path.name}：{result.stderr.strip() or result.stdout.strip()}")
    members: list[tuple[str, int]] = []
    record: dict[str, str] = {}
    for line in [*result.stdout.splitlines(), ""]:
        if not line.strip():
            member = record.get("Path", "")
            if member.lower().endswith(".dem"):
                members.append((member, int(record.get("Size", "0"))))
            record = {}
        elif " = " in line:
            key, value = line.split(" = ", 1)
            record[key] = value
    return members


def _map_name(value: str) -> str:
    lower = Path(value).stem.lower()
    match = re.search(r"(?:^|[-_])(?:de_)?(" + "|".join(MAP_NAMES) + r")(?:$|[-_])", lower)
    return f"de_{match.group(1)}" if match else "unknown"


def _match_slug(path: Path) -> str:
    stem = path.stem
    return re.sub(r"-bo[135]-.*$", "", stem, flags=re.IGNORECASE)


def _catalog_rows(source_dir: Path, target_map: str) -> list[dict[str, object]]:
    seven_zip = _find_7z()
    rows: list[dict[str, object]] = []
    for source in sorted(source_dir.rglob("*")):
        if not source.is_file():
            continue
        suffix = source.suffix.lower()
        if suffix == ".dem":
            members = [(source.name, source.stat().st_size)]
            source_kind = "single_demo"
        elif suffix in ARCHIVE_SUFFIXES:
            members = _archive_members(source, seven_zip)
            source_kind = "match_archive"
        else:
            continue
        for member, demo_size in members:
            map_name = _map_name(member)
            rows.append(
                {
                    "source_file": str(source.resolve()),
                    "source_kind": source_kind,
                    "match_slug": _match_slug(source),
                    "demo_member": member,
                    "map": map_name,
                    "is_target_map": map_name == target_map,
                    "demo_size_bytes": demo_size,
                    "duplicate_key": f"{Path(member).name.lower()}::{demo_size}",
                    "catalog_status": "filename_indexed_not_parsed",
                }
            )
    duplicate_keys = {
        key for key in {str(row["duplicate_key"]) for row in rows}
        if sum(row["duplicate_key"] == key for row in rows) > 1
    }
    for row in rows:
        if row["duplicate_key"] in duplicate_keys:
            row["catalog_status"] = (
                "duplicate_member_candidate" if row["source_kind"] == "single_demo"
                else "filename_indexed_not_parsed"
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = ["source_file", "source_kind", "match_slug", "demo_member", "map", "is_target_map", "demo_size_bytes", "duplicate_key", "catalog_status"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="按地图建立 CS2 整场 Demo 下载包的可追溯索引")
    parser.add_argument("source", type=Path, help="存放 .rar/.zip/.dem 的原始目录")
    parser.add_argument("--team", required=True, help="本次整理的目标队伍，仅写入目录元数据")
    parser.add_argument("--target-map", required=True, help="关注地图，例如 de_mirage")
    parser.add_argument("--output", type=Path, required=True, help="索引输出目录")
    args = parser.parse_args()
    if not args.source.is_dir():
        parser.error(f"找不到原始目录：{args.source}")

    target_map = args.target_map.strip().lower()
    rows = _catalog_rows(args.source, target_map)
    if not rows:
        parser.error("没有找到 .dem、.rar、.7z 或 .zip 文件")

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "all_maps.csv", rows)
    target_rows = [row for row in rows if row["is_target_map"]]
    _write_csv(output / f"{target_map}.csv", target_rows)
    maps_root = output / "maps"
    map_counts: dict[str, int] = {}
    for map_name in sorted({str(row["map"]) for row in rows}):
        map_rows = [row for row in rows if row["map"] == map_name]
        category = maps_root / map_name
        category.mkdir(parents=True, exist_ok=True)
        _write_csv(category / "demos.csv", map_rows)
        (category / "category.json").write_text(
            json.dumps(
                {
                    "team": args.team,
                    "map": map_name,
                    "demo_entries": len(map_rows),
                    "unique_demo_candidates": len({row["duplicate_key"] for row in map_rows}),
                    "boundary": "按原始包目录和文件名分类；尚未解析，不可当作已校验的比赛数据。",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        map_counts[map_name] = len(map_rows)
    summary = {
        "team": args.team,
        "target_map": target_map,
        "source_directory": str(args.source.resolve()),
        "source_match_files": len({row["source_file"] for row in rows}),
        "demo_entries": len(rows),
        "target_map_entries": len(target_rows),
        "target_map_unique_candidates": len({row["duplicate_key"] for row in target_rows}),
        "maps": map_counts,
        "map_category_root": str(maps_root.resolve()),
        "boundary": "文件名索引，不代表解析完成；队伍、地图和阵容会在实际导入 .dem 时再次校验。",
    }
    (output / "catalog_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已建立索引：{output}")
    print(f"{args.team} · {len(rows)} 张地图 Demo · {target_map} {len(target_rows)} 张")


if __name__ == "__main__":
    main()
