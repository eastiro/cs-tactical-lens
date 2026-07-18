"""Build a lightweight, publicly redistributable showcase bundle from a real match.

Reads a fully normalized bundle from ``data/processed/``, copies all event
tables verbatim, downsamples the position track to 8 Hz, strips absolute
paths from metadata, and writes a compressed ``positions.csv.gz``.

Usage:
    python scripts/build_showcase_bundle.py ^
        --source data/processed/iem-cologne-major-2026-corpus/2395002/de_mirage ^
        --output data/showcase/furia-falcons-mirage ^
        --position-hz 8

The output is fully reproducible: same input produces identical content.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

EVENT_TABLES = (
    "rounds.csv",
    "kills.csv",
    "grenades.csv",
    "damages.csv",
    "bomb_events.csv",
    "economy_snapshots.csv",
    "loadout_events.csv",
)

SENSITIVE_PATTERNS = (
    "source_archive",
    "source_member",
    "provisional_member_map",
    "map_label_corrected",
    "importer",
    "imported_at",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a lightweight public showcase bundle from a real match."
    )
    parser.add_argument("--source", type=Path, required=True,
                        help="Source normalized bundle path")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output directory for the showcase bundle")
    parser.add_argument("--position-hz", type=int, default=8,
                        choices=(1, 2, 4, 8, 16, 32, 64),
                        help="Target position sampling rate in Hz (default 8)")
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_table(src: Path, dst: Path, name: str) -> dict:
    """Copy a CSV table verbatim. Returns row count and size."""
    src_path = src / name
    dst_path = dst / name
    if not src_path.is_file():
        return {"name": name, "status": "missing", "rows": 0, "bytes": 0}
    shutil.copy2(str(src_path), str(dst_path))
    with dst_path.open(encoding="utf-8") as f:
        row_count = sum(1 for _ in csv.DictReader(f))
    return {
        "name": name,
        "status": "copied",
        "rows": row_count,
        "bytes": dst_path.stat().st_size,
        "sha256_src": _sha256(src_path),
        "sha256_out": _sha256(dst_path),
    }


def _downsample_positions(src: Path, dst: Path, target_hz: int) -> dict:
    """Downsample positions to target_hz and write as positions.csv.gz.

    Keeps first and last sample per round+player, plus every Nth source tick.
    No averaging, no interpolation.
    """
    source_interval = 64 // target_hz  # ticks between keepers
    with src.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total_in = len(rows)

    # Group by round+player
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(int(row["round"]), row["player"])].append(row)

    selected: list[dict] = []
    for key, group_rows in sorted(groups.items()):
        group_rows.sort(key=lambda r: (int(r["round"]), int(r["tick"])))
        # Always keep first and last
        keep_indices = {0, len(group_rows) - 1}
        for idx, row in enumerate(group_rows):
            tick = int(row["tick"])
            if (tick % source_interval) == 0:
                keep_indices.add(idx)
        selected.extend(
            group_rows[i] for i in sorted(keep_indices)
        )

    # Write gzipped CSV
    # Pin the gzip timestamp so identical inputs produce identical bytes.
    with dst.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as gz:
                writer = csv.DictWriter(gz, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(selected)

    total_out = len(selected)
    return {
        "name": "positions.csv.gz",
        "source_rows": total_in,
        "output_rows": total_out,
        "compression_ratio": round(total_in / max(total_out, 1), 2),
        "target_hz": target_hz,
        "source_interval_ticks": source_interval,
        "bytes": dst.stat().st_size,
        "sha256_out": _sha256(dst),
    }


def _contains_local_path(value: str) -> bool:
    """Return whether text exposes a local absolute filesystem path."""
    text = str(value).strip()
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", text)
        or text.startswith(("/home/", "/Users/", "\\\\"))
        or "EASTIRO" in text
        or "好玩的项目" in text
    )


def _sanitize_value(value: object) -> object | None:
    """Recursively remove local paths while preserving public metadata."""
    if isinstance(value, dict):
        return {
            str(key): cleaned
            for key, item in value.items()
            if str(key) not in SENSITIVE_PATTERNS
            and (cleaned := _sanitize_value(item)) is not None
        }
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _sanitize_value(item)) is not None]
    if isinstance(value, str) and _contains_local_path(value):
        return None
    return value


def _sanitize_metadata(
    src_meta: Path,
    dst_meta: Path,
    match_id: str,
    target_hz: int,
) -> dict:
    """Read source metadata, strip absolute paths, add showcase markers."""
    raw = json.loads(src_meta.read_text(encoding="utf-8"))

    clean = _sanitize_value(raw)
    if not isinstance(clean, dict):
        raise ValueError("metadata.json must contain an object")

    # Add showcase markers
    clean["showcase"] = True
    clean["showcase_source_match_id"] = match_id
    interval = 64 // target_hz
    clean["position_sample_hz"] = target_hz
    clean["position_sampling"] = (
        f"first/last per round-player + every {interval} source ticks"
    )
    clean["full_corpus_included"] = False

    dst_meta.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "name": "metadata.json",
        "bytes": dst_meta.stat().st_size,
        "sha256_out": _sha256(dst_meta),
    }


def _verify_no_sensitive_paths(output: Path) -> list[str]:
    """Scan all output files for sensitive path patterns."""
    issues: list[str] = []
    patterns = [r"D:\\", r"C:\\", r"\\Users\\", "EASTIRO", "好玩的项目"]
    for f in output.rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            if pat in text:
                # Show context
                for i, line in enumerate(text.splitlines(), 1):
                    if pat in line:
                        issues.append(f"{f.name}:{i}: {line.strip()[:120]}")
    return issues


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    source = args.source.resolve()
    output = args.output.resolve()
    target_hz = args.position_hz

    if not source.is_dir():
        print(f"Error: source not found: {source}", file=sys.stderr)
        sys.exit(1)
    if not (source / "metadata.json").is_file():
        print(f"Error: source has no metadata.json: {source}", file=sys.stderr)
        sys.exit(1)

    # Safety: source and output may not contain one another.  Otherwise the
    # final replacement could overwrite or recursively delete the source.
    if output == source or source in output.parents or output in source.parents:
        print("Error: source and output directories must be disjoint", file=sys.stderr)
        sys.exit(1)

    source_hashes_before = {
        path.name: _sha256(path)
        for path in sorted(source.iterdir())
        if path.is_file()
    }

    # Build in temp dir, then replace atomically
    with tempfile.TemporaryDirectory(prefix="showcase_") as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir(parents=True, exist_ok=True)

        # ── Copy event tables ──
        table_report: list[dict] = []
        for name in EVENT_TABLES:
            table_report.append(_copy_table(source, staging, name))

        # ── Downsample positions → positions.csv.gz ──
        pos_src = source / "positions.csv"
        pos_dst = staging / "positions.csv.gz"
        if pos_src.is_file():
            pos_report = _downsample_positions(pos_src, pos_dst, target_hz)
        else:
            pos_report = {"name": "positions.csv.gz", "status": "missing"}
        table_report.append(pos_report)

        # ── Metadata ──
        meta_dst = staging / "metadata.json"
        src_meta = source / "metadata.json"
        src_raw = json.loads(src_meta.read_text(encoding="utf-8"))
        match_id = str(src_raw.get("match_id", "unknown"))
        meta_report = _sanitize_metadata(src_meta, meta_dst, match_id, target_hz)

        # ── Manifest ──
        total_bytes = sum(
            (staging / t["name"]).stat().st_size
            for t in table_report
            if "name" in t and (staging / t["name"]).is_file()
        )

        manifest = {
            "showcase": True,
            "showcase_version": "1.0",
            "source_match_id": match_id,
            "files": table_report + [meta_report],
            "position_sampling_hz": target_hz,
            "position_sampling_rule": (
                f"first/last per round-player + every {64 // target_hz} source ticks"
            ),
            "total_bytes": total_bytes,
            "reproducible": True,
            "source_sha256": source_hashes_before,
        }
        (staging / "showcase_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ── Privacy scan ──
        sensitive = _verify_no_sensitive_paths(staging)
        if sensitive:
            print("ERROR: Sensitive paths found in output!", file=sys.stderr)
            for s in sensitive:
                print(f"  {s}", file=sys.stderr)
            sys.exit(1)

        source_hashes_after = {
            path.name: _sha256(path)
            for path in sorted(source.iterdir())
            if path.is_file()
        }
        if source_hashes_after != source_hashes_before:
            print("ERROR: source bundle changed during export", file=sys.stderr)
            sys.exit(1)

        if sum(path.stat().st_size for path in staging.rglob("*") if path.is_file()) > 30 * 1024 * 1024:
            print("ERROR: showcase bundle exceeds the 30 MB hard limit", file=sys.stderr)
            sys.exit(1)

        # ── Atomic replace ──
        if output.is_dir():
            shutil.rmtree(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output)

    # ── Final report (from the now-permanent output) ──
    final_manifest = json.loads((output / "showcase_manifest.json").read_text(encoding="utf-8"))
    total_mb = final_manifest["total_bytes"] / 1024 / 1024

    print("=" * 60)
    print("Showcase bundle created")
    print("=" * 60)
    print(f"  Source:      {source}")
    print(f"  Output:      {output}")
    print(f"  Total size:  {total_mb:.2f} MB")
    print()
    print("  Files:")
    for entry in final_manifest["files"]:
        name = entry["name"]
        size_kb = entry.get("bytes", 0) / 1024
        if "rows" in entry:
            print(f"    {name:30s} {size_kb:>8.1f} KB  ({entry['rows']} rows)")
        elif "output_rows" in entry:
            print(f"    {name:30s} {size_kb:>8.1f} KB  ({entry['output_rows']} rows, {entry.get('compression_ratio','?')}x compression)")
        else:
            print(f"    {name:30s} {size_kb:>8.1f} KB")
    print()
    if total_mb > 30:
        print(f"  WARNING: Showcase exceeds 30 MB hard limit ({total_mb:.2f} MB)")
        sys.exit(1)
    elif total_mb > 20:
        print(f"  WARNING: Showcase is {total_mb:.2f} MB (target <=20 MB, within hard 30 MB limit)")
    else:
        print(f"  OK: Showcase within 20 MB target ({total_mb:.2f} MB)")


if __name__ == "__main__":
    main()
