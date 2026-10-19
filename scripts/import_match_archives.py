"""Extract selected map demos from full-match archives and build bundles.

The archive remains untouched.  Only the requested member (for example the
Mirage map) is streamed to a temporary file, parsed, validated, then written
as a normalized bundle.  Use ``--dry-run`` first when working with a batch of
large BO3/BO5 downloads.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_match_archives import _find_7z  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.awpy_adapter import load_awpy_demo, write_normalized_bundle  # noqa: E402
from src.schema import MatchData, validate_match  # noqa: E402


def _alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().removeprefix("team "))


TEAM_ALIASES = {
    "falcons": {"falcons", "flc"},
    "aurora": {"aurora", "aurora gaming"},
    "betboom": {"betboom", "betboom team"},
    "fut": {"fut", "fut esports"},
    "legacy": {"legacy", "lgcy"},
    "natus vincere": {"natus vincere", "navi"},
    "the mongolz": {"the mongolz", "mongolz", "mglz"},
    "g2": {"g2", "g2 esports"},
    "furia": {"furia"},
    "spirit": {"spirit", "team spirit"},
    "mouz": {"mouz"},
    "monte": {"monte"},
    "pain": {"pain", "pain gaming"},
    "9z": {"9z", "9z globant"},
}

PLAYER_ALIASES = {
    "sh1ro": {"sh1ro", "sh1r0"},
}


def _team_matches(expected: str, actual: str) -> bool:
    expected_alias = _alias(expected)
    actual_alias = _alias(actual)
    aliases = TEAM_ALIASES.get(expected_alias, {expected_alias})
    if actual_alias in aliases:
        return True
    # Official demo labels often append an organisation suffix while the
    # registry uses the short competitive name (for example FUT Esports,
    # paiN Gaming, BetBoom Team).  Treat only these generic suffixes as
    # cosmetic; all other names still require an explicit alias above.
    suffix_pattern = r"\s+(?:esports|gaming|team)$"
    return re.sub(suffix_pattern, "", actual_alias) in aliases


def _player_matches(expected: str, actual: str) -> bool:
    expected_alias = expected.strip().lower()
    actual_alias = actual.strip().lower()
    return actual_alias in PLAYER_ALIASES.get(expected_alias, {expected_alias})


def _registry(path: Path) -> dict[str, dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["match_slug"]): row for row in raw.get("matches", [])}


def _known_team_name(value: object) -> str | None:
    """Keep real parser labels, but discard missing-value strings from summaries."""
    normalized = str(value).strip()
    if not normalized or normalized.lower() in {"none", "nan", "null"}:
        return None
    return normalized


def _observed_team_names(data: MatchData) -> list[str]:
    """Collect team names from summaries and event tables.

    Some official demos have an incomplete round summary (for example
    ``team_b == 'None'``) while positions, kills, and freeze-end snapshots
    still retain the actual clan label.  This is a fallback for evidence that
    already exists inside the parsed demo, not a filename-based guess.
    """
    names: set[str] = set()
    for value in (data.team_a, data.team_b):
        if known := _known_team_name(value):
            names.add(known)
    sources = (
        (data.positions, ("team",)),
        (data.kills, ("attacker_team", "victim_team")),
        (data.grenades, ("team",)),
        (data.damages, ("attacker_team", "victim_team")),
        (data.economy_snapshots, ("team",)),
        (data.loadout_events, ("team",)),
    )
    for frame, columns in sources:
        for column in columns:
            if column not in frame.columns:
                continue
            for value in frame[column].dropna().unique():
                if known := _known_team_name(value):
                    names.add(known)
    return sorted(names)


def _read_candidates(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        if str(row.get("is_target_map", "")).lower() != "true":
            continue
        key = row["duplicate_key"]
        current = selected.get(key)
        # Prefer an archive member over an already extracted loose duplicate.
        if current is None or current["source_kind"] == "single_demo":
            selected[key] = row
    return sorted(selected.values(), key=lambda row: (row["match_slug"], row["demo_member"]))


def _extract_one(row: dict[str, str], destination: Path, seven_zip: str | None) -> Path:
    source = Path(row["source_file"])
    if row["source_kind"] == "single_demo":
        return source
    if not seven_zip:
        raise RuntimeError("需要 7-Zip 才能从 RAR/7z 整场包抽取单张地图。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        result = subprocess.run(
            [seven_zip, "e", "-so", str(source), row["demo_member"]],
            stdout=handle,
            stderr=subprocess.PIPE,
            text=False,
        )
    if result.returncode:
        raise RuntimeError(
            f"抽取失败：{source.name} / {row['demo_member']}：{result.stderr.decode(errors='replace').strip()}"
        )
    return destination


def _validate(data, row: dict[str, str], registry_entry: dict[str, object], target_team: str, expected_players: set[str]) -> None:
    if str(data.map_name).strip().lower() != row["map"].lower():
        raise ValueError(f"地图校验失败：目录写 {row['map']}，解析出 {data.map_name}")
    expected_teams = [str(team) for team in registry_entry["teams"]]
    actual_teams = _observed_team_names(data)
    if not all(any(_team_matches(expected, actual) for actual in actual_teams) for expected in expected_teams):
        raise ValueError(f"队伍校验失败：清单为 {sorted(expected_teams)}，Demo 为 {sorted(actual_teams)}")
    target_actual = next((team for team in actual_teams if _team_matches(target_team, team)), None)
    if target_actual is None:
        raise ValueError(f"目标队伍不在 Demo 中：{target_team}")
    observed = {
        str(player).strip().lower()
        for player in data.positions.loc[data.positions["team"] == target_actual, "player"].dropna().unique()
    }
    missing = {
        expected
        for expected in expected_players
        if not any(_player_matches(expected, actual) for actual in observed)
    }
    if missing:
        raise ValueError(
            f"{target_team} 阵容校验失败，缺少：{', '.join(sorted(missing))}；"
            f"Demo 中观察到：{', '.join(sorted(observed))}"
        )


def _canonicalize_team_names(data: MatchData, registry_entry: dict[str, object]) -> MatchData:
    """Rewrite parser abbreviations to registry names while preserving raw names."""
    expected = [str(team) for team in registry_entry["teams"]]
    actual = _observed_team_names(data)
    mapping: dict[str, str] = {}
    for expected_name in expected:
        match = next((actual_name for actual_name in actual if _team_matches(expected_name, actual_name)), None)
        if match is None:
            raise ValueError(f"无法建立队伍正式名映射：{expected_name} vs {actual}")
        mapping[match] = expected_name

    def mapped(frame, columns: tuple[str, ...]):
        result = frame.copy()
        for column in columns:
            if column in result.columns:
                result[column] = result[column].map(mapping).fillna(result[column])
        return result

    metadata = {
        **data.metadata,
        "raw_team_a": data.team_a,
        "raw_team_b": data.team_b,
        "team_names_canonicalized": True,
    }
    canonical = MatchData(
        data.match_name,
        data.map_name,
        expected[0],
        expected[1],
        data.source_kind,
        mapped(data.rounds, ("winner",)),
        mapped(data.kills, ("attacker_team", "victim_team")),
        mapped(data.positions, ("team",)),
        mapped(data.grenades, ("team",)),
        metadata=metadata,
        damages=mapped(data.damages, ("attacker_team", "victim_team")),
        bomb_events=mapped(data.bomb_events, ("team",)),
        economy_snapshots=mapped(data.economy_snapshots, ("team",)),
        loadout_events=mapped(data.loadout_events, ("team",)),
    )
    validate_match(canonical)
    return canonical


def main() -> None:
    parser = argparse.ArgumentParser(description="从整场 CS2 Demo 包中抽取、校验并批量生成地图 bundle")
    parser.add_argument("catalog", type=Path, help="按地图生成的 demos.csv，例如 de_mirage/demos.csv")
    parser.add_argument("--registry", type=Path, required=True, help="比赛双方、赛事和日期 JSON")
    parser.add_argument("--output", type=Path, required=True, help="bundle 输出根目录")
    parser.add_argument("--target-team", default="Team Falcons")
    parser.add_argument("--expected-players", default="karrigan,NiKo,TeSeS,m0NESY,kyousuke")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 场，0 表示全部")
    parser.add_argument("--dry-run", action="store_true", help="只显示去重后的抽取队列，不解压、不解析")
    args = parser.parse_args()
    candidates = _read_candidates(args.catalog)
    registry = _registry(args.registry)
    candidates = [row for row in candidates if row["match_slug"] in registry]
    if args.limit:
        candidates = candidates[:args.limit]
    if not candidates:
        parser.error("没有找到已登记且目标地图匹配的 Demo")

    pending: list[dict[str, str]] = []
    validated_results: list[dict[str, str]] = []
    skipped = 0
    for row in candidates:
        metadata_path = args.output / row["match_slug"] / row["map"] / "metadata.json"
        if metadata_path.is_file():
            try:
                if (
                    json.loads(metadata_path.read_text(encoding="utf-8")).get("import_status") == "parsed_and_validated"
                    and json.loads(metadata_path.read_text(encoding="utf-8")).get("team_names_canonicalized")
                ):
                    skipped += 1
                    validated_results.append(
                        {
                            "match_slug": row["match_slug"],
                            "map": row["map"],
                            "bundle": str(args.output / row["match_slug"] / row["map"]),
                            "status": "parsed_and_validated",
                        }
                    )
                    continue
            except (OSError, json.JSONDecodeError):
                pass
        pending.append(row)
    candidates = pending
    print(f"待处理：{len(candidates)} 场 {args.catalog.stem}（已跳过已校验 {skipped} 场）")
    if not candidates:
        print("没有新的 Demo 需要导入。")
        args.output.mkdir(parents=True, exist_ok=True)
        deduped_validated: dict[tuple[str, str], dict[str, str]] = {}
        for result in validated_results:
            deduped_validated[(result["match_slug"], result["map"])] = result
        with (args.output / "import_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["match_slug", "map", "bundle", "status"])
            writer.writeheader()
            writer.writerows(deduped_validated.values())
        return
    for index, row in enumerate(candidates, start=1):
        print(f"{index:02d}. {row['match_slug']} <- {Path(row['source_file']).name} :: {row['demo_member']}")
    if args.dry_run:
        return

    seven_zip = _find_7z()
    expected_players = {player.strip().lower() for player in args.expected_players.split(",") if player.strip()}
    results: list[dict[str, str]] = list(validated_results)
    for index, row in enumerate(candidates, start=1):
        registry_entry = registry[row["match_slug"]]
        with tempfile.TemporaryDirectory(prefix="cs-demo-") as temp_dir:
            demo_path = _extract_one(row, Path(temp_dir) / row["demo_member"], seven_zip)
            data = load_awpy_demo(demo_path)
            _validate(data, row, registry_entry, args.target_team, expected_players)
            data = _canonicalize_team_names(data, registry_entry)
            bundle = args.output / row["match_slug"] / row["map"]
            write_normalized_bundle(data, bundle)
            metadata_path = bundle / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata.update({
                "source_archive": row["source_file"],
                "source_member": row["demo_member"],
                "event": registry_entry.get("event", ""),
                "date": registry_entry.get("date", ""),
                "target_team": args.target_team,
                "import_status": "parsed_and_validated",
            })
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append({"match_slug": row["match_slug"], "map": row["map"], "bundle": str(bundle), "status": "parsed_and_validated"})
            print(f"[{index}/{len(candidates)}] 已完成：{row['match_slug']}")

    # A split map (for example p1/p2) can produce multiple catalog rows for one
    # match.  Keep one import-results row per match/map so downstream manifests
    # never count a segmented Demo as multiple matches.
    deduped_results: dict[tuple[str, str], dict[str, str]] = {}
    for result in results:
        deduped_results[(result["match_slug"], result["map"])] = result
    results = list(deduped_results.values())

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "import_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["match_slug", "map", "bundle", "status"])
        writer.writeheader()
        writer.writerows(results)
    print(f"完成：{len(results)} 场已解析并校验。")


if __name__ == "__main__":
    main()
