#!/usr/bin/env python3
"""Resume-safe downloader for the IEM Cologne Major 2026 research corpus.

The script deliberately treats an HLTV match ID as the deduplication key.  A
demo archive's filename is not reliable enough: names can vary while the same
match remains the same source.  It resolves the demo ID from each public match
page, writes each archive into its tournament-stage folder, and persists a
state file after every completed match so it can be safely restarted.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "intake-seeds" / "iem-cologne-major-2026-stage2-stage3-match-pages.json"
DEFAULT_OUTPUT = ROOT / "data" / "raw" / "iem-cologne-major-2026"
DEFAULT_STATE = ROOT / "reports" / "iem-cologne-major-2026-download-state.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# These are tournament playoffs, not part of the Swiss-stage seed file.
PLAYOFFS = [
    ("2394996", "Aurora vs BetBoom", "https://www.hltv.org/matches/2394996/aurora-vs-betboom-iem-cologne-major-2026"),
    ("2394997", "9z vs FURIA", "https://www.hltv.org/matches/2394997/9z-vs-furia-iem-cologne-major-2026"),
    ("2394998", "G2 vs Spirit", "https://www.hltv.org/matches/2394998/g2-vs-spirit-iem-cologne-major-2026"),
    ("2394999", "Falcons vs Vitality", "https://www.hltv.org/matches/2394999/falcons-vs-vitality-iem-cologne-major-2026"),
    ("2395000", "Aurora vs FURIA", "https://www.hltv.org/matches/2395000/aurora-vs-furia-iem-cologne-major-2026"),
    ("2395001", "Spirit vs Falcons", "https://www.hltv.org/matches/2395001/spirit-vs-falcons-iem-cologne-major-2026"),
    ("2395002", "FURIA vs Falcons", "https://www.hltv.org/matches/2395002/furia-vs-falcons-iem-cologne-major-2026"),
]

# Archives already in data/raw when this corpus job was created.
PRESENT_MATCH_IDS = {
    "2394888",  # Stage 2: Spirit vs 9z
    "2394982",  # Stage 3: Falcons vs Monte
    "2394986",  # Stage 3: Spirit vs 9z
    "2394991",  # Stage 3: NAVI vs Falcons
    "2394998",  # playoffs: G2 vs Spirit
    "2395001",  # playoffs: Spirit vs Falcons
    "2395002",  # playoffs: FURIA vs Falcons
}


def run_curl(args: list[str]) -> subprocess.CompletedProcess[str]:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required but was not found on PATH")
    return subprocess.run([curl, *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")


def read_seed(path: Path) -> list[dict[str, str]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    matches: list[dict[str, str]] = []
    for stage_key, records in source["stages"].items():
        for record in records:
            matches.append({**record, "stage": stage_key})
    for match_id, teams, url in PLAYOFFS:
        matches.append({"match_id": match_id, "teams": teams, "url": url, "stage": "playoffs"})
    return matches


def resolve_demo(record: dict[str, str]) -> tuple[str, str]:
    page = run_curl(["-fsSL", "--retry", "2", "--connect-timeout", "20", "--max-time", "45", "-A", USER_AGENT, record["url"]])
    if page.returncode:
        raise RuntimeError(f"match page request failed: {page.stderr.strip()}")
    found = re.search(r'data-demo-link="/download/demo/(\d+)"', page.stdout)
    if not found:
        raise RuntimeError("HLTV page did not expose a demo link")
    demo_id = found.group(1)
    headers = run_curl(["-fsSIL", "--connect-timeout", "20", "--max-time", "45", "-A", USER_AGENT, f"https://www.hltv.org/download/demo/{demo_id}"])
    if headers.returncode:
        raise RuntimeError(f"demo redirect request failed: {headers.stderr.strip()}")
    locations = re.findall(r"(?im)^location:\s*(\S+)", headers.stdout)
    if not locations:
        raise RuntimeError("demo endpoint returned no archive redirect")
    return demo_id, locations[-1]


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "completed": {}, "skipped_existing": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--limit", type=int, help="download at most this many missing matches")
    parser.add_argument("--match-id", help="only process one known match ID (for validation/recovery)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = load_state(args.state)
    matches = read_seed(args.seed)
    seen = set()
    matches = [m for m in matches if not (m["match_id"] in seen or seen.add(m["match_id"]))]
    if args.match_id:
        matches = [m for m in matches if m["match_id"] == args.match_id]
        if not matches:
            raise SystemExit(f"match ID {args.match_id} is not in the source manifest")
    downloaded = 0

    for record in matches:
        match_id = record["match_id"]
        if match_id in PRESENT_MATCH_IDS:
            state["skipped_existing"][match_id] = {"teams": record["teams"], "reason": "already present before corpus job"}
            continue
        if match_id in state["completed"]:
            continue
        if args.limit is not None and downloaded >= args.limit:
            break

        print(f"[{downloaded + 1}] {record['stage']} | {record['teams']} | match {match_id}", flush=True)
        try:
            demo_id, archive_url = resolve_demo(record)
            name = archive_url.rsplit("/", 1)[-1]
            target_dir = args.output / record["stage"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / name
            partial = target.with_suffix(target.suffix + ".part")
            if args.dry_run:
                print(f"  demo {demo_id}: {name}", flush=True)
                downloaded += 1
                continue
            if not target.exists():
                result = run_curl([
                    "-fL", "--retry", "5", "--retry-all-errors", "--connect-timeout", "20", "--max-time", "900", "--continue-at", "-",
                    "-A", USER_AGENT, "-e", record["url"], "--output", str(partial), archive_url,
                ])
                if result.returncode:
                    raise RuntimeError(f"archive download failed: {result.stderr.strip()}")
                partial.replace(target)
            state["completed"][match_id] = {
                "teams": record["teams"], "stage": record["stage"], "demo_id": demo_id,
                "archive": str(target.relative_to(ROOT)).replace("\\", "/"),
            }
            state.get("errors", {}).pop(match_id, None)
            save_state(args.state, state)
            downloaded += 1
        except Exception as exc:  # keep completed prior files; record then continue
            state.setdefault("errors", {})[match_id] = {"teams": record["teams"], "error": str(exc)}
            save_state(args.state, state)
            print(f"  ERROR: {exc}", file=sys.stderr, flush=True)

    save_state(args.state, state)
    print(json.dumps({"total_sources": len(matches), "already_present": len(state["skipped_existing"]), "completed": len(state["completed"]), "errors": len(state.get("errors", {}))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
