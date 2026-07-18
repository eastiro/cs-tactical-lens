"""Read-only coverage audit for future team-map research ranges."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .research_catalog import ResearchProfile, discover_research_profiles, evidence_bundle_index


@dataclass(frozen=True)
class CoverageRow:
    profile_id: str
    team: str
    map_name: str
    season: str
    complete_matches: int
    eligible_samples: int
    pairable: bool
    matches_to_threshold: int


def _metadata(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def normalized_bundles(processed_root: str | Path) -> tuple[Path, ...]:
    """Find parsed bundle folders without changing any data."""
    root = Path(processed_root)
    bundles = [path.parent.resolve() for path in root.rglob("metadata.json") if _metadata(path)]
    return tuple(sorted(set(bundles)))


def coverage_rows(series_root: str | Path, *, threshold: int = 5) -> tuple[CoverageRow, ...]:
    """Summarise only complete, selectable series and comparison readiness."""
    profiles = discover_research_profiles(series_root)
    teams_by_map: dict[str, set[str]] = {}
    for profile in profiles:
        if profile.match_count >= threshold:
            teams_by_map.setdefault(profile.map_name.lower(), set()).add(profile.team.lower())
    rows = []
    for profile in profiles:
        pairable = len(teams_by_map.get(profile.map_name.lower(), set())) >= 2 and profile.match_count >= threshold
        rows.append(CoverageRow(
            profile_id=profile.profile_id,
            team=profile.team,
            map_name=profile.map_name,
            season=profile.season,
            complete_matches=profile.match_count,
            eligible_samples=profile.eligible_samples,
            pairable=pairable,
            matches_to_threshold=max(0, threshold - profile.match_count),
        ))
    return tuple(rows)


def unassigned_bundles(series_root: str | Path, processed_root: str | Path) -> tuple[Path, ...]:
    """Return parsed bundles not referenced by any complete series manifest."""
    profiles = discover_research_profiles(series_root)
    assigned = {path.resolve() for path in evidence_bundle_index(profiles).values()}
    return tuple(path for path in normalized_bundles(processed_root) if path not in assigned)
