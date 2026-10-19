"""Auditable discovery helpers for the multi-team research workspace.

This module owns *which* completed team-map series are selectable and which
bundle belongs to a particular evidence row.  It deliberately does not parse
Demos or calculate structures: those responsibilities stay with the existing
series and comparison modules.

The key for an evidence bundle is ``(profile_id, match_id)`` rather than only
``match_id``.  The same real match can legitimately occur in two teams'
series; reducing it to a global match id makes the provenance of a replay
ambiguous.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED_ARTIFACTS = (
    "series_metadata.json",
    "precontact_opening_samples.csv",
    "precontact_opening_profile.csv",
)


@dataclass(frozen=True)
class ResearchProfile:
    """One complete, locally auditable team-map series."""

    profile_id: str
    team: str
    map_name: str
    season: str
    manifest_path: Path
    series_dir: Path
    match_count: int
    eligible_samples: int


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _series_dir_for_manifest(manifest_path: Path) -> Path:
    """Return the artifact folder paired with ``foo.json`` -> ``foo/``."""
    return manifest_path.with_suffix("")


def discover_research_profiles(series_root: str | Path) -> tuple[ResearchProfile, ...]:
    """Return only complete profiles, in a stable map/team/id order.

    Incomplete manifests are intentionally ignored instead of becoming empty
    UI options.  This lets data collection progress independently without
    making the workspace promise a comparison it cannot support yet.
    """
    root = Path(series_root)
    profiles: list[ResearchProfile] = []
    for manifest_path in sorted(root.glob("*.json")):
        if manifest_path.name.endswith(".example.json"):
            continue
        series_dir = _series_dir_for_manifest(manifest_path)
        if not all((series_dir / name).is_file() for name in REQUIRED_ARTIFACTS):
            continue
        manifest = _read_json(manifest_path)
        metadata = _read_json(series_dir / "series_metadata.json")
        if manifest is None or metadata is None:
            continue
        team = str(manifest.get("team", "")).strip()
        map_name = str(manifest.get("map", "")).strip()
        if not team or not map_name:
            continue
        profiles.append(
            ResearchProfile(
                profile_id=manifest_path.stem,
                team=team,
                map_name=map_name,
                season=str(manifest.get("season", "")).strip(),
                manifest_path=manifest_path,
                series_dir=series_dir,
                match_count=_nonnegative_int(metadata.get("match_count")),
                eligible_samples=_nonnegative_int(metadata.get("eligible_precontact_samples")),
            )
        )
    return tuple(sorted(profiles, key=lambda item: (item.map_name.lower(), item.team.lower(), item.profile_id)))


def maps_with_pairable_profiles(profiles: tuple[ResearchProfile, ...]) -> tuple[str, ...]:
    """Return maps that have at least two distinct teams ready to compare."""
    teams_by_map: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for profile in profiles:
        key = profile.map_name.lower()
        teams_by_map.setdefault(key, set()).add(profile.team.lower())
        labels.setdefault(key, profile.map_name)
    return tuple(labels[key] for key in sorted(labels) if len(teams_by_map[key]) >= 2)


def profiles_for_map(
    profiles: tuple[ResearchProfile, ...], map_name: str
) -> tuple[ResearchProfile, ...]:
    """Return all ready profiles for exactly one map (case-insensitive)."""
    wanted = str(map_name).strip().lower()
    return tuple(profile for profile in profiles if profile.map_name.lower() == wanted)


def opponent_profiles(
    profiles: tuple[ResearchProfile, ...], selected: ResearchProfile
) -> tuple[ResearchProfile, ...]:
    """Return same-map profiles for a different team than ``selected``."""
    return tuple(
        profile
        for profile in profiles_for_map(profiles, selected.map_name)
        if profile.team.lower() != selected.team.lower()
    )


def load_profile_artifacts(
    profile: ResearchProfile,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    """Load a profile's already-built artifacts without reparsing any Demo."""
    metadata = _read_json(profile.series_dir / "series_metadata.json")
    if metadata is None:
        raise ValueError(f"研究 series 元数据不可读取：{profile.profile_id}")
    samples = pd.read_csv(profile.series_dir / "precontact_opening_samples.csv")
    opening_profile = pd.read_csv(profile.series_dir / "precontact_opening_profile.csv")
    return metadata, samples, opening_profile


def evidence_bundle_index(
    profiles: tuple[ResearchProfile, ...],
) -> dict[tuple[str, str], Path]:
    """Map a profile-scoped evidence key to a verified local bundle folder.

    A missing or malformed match entry is omitted.  Importantly, duplicate
    match ids across different profiles are retained as separate keys.
    """
    index: dict[tuple[str, str], Path] = {}
    for profile in profiles:
        manifest = _read_json(profile.manifest_path)
        if manifest is None:
            continue
        matches = manifest.get("matches", [])
        if not isinstance(matches, list):
            continue
        for entry in matches:
            if not isinstance(entry, dict):
                continue
            match_id = str(entry.get("id", "")).strip()
            raw_bundle = str(entry.get("bundle", "")).strip()
            if not match_id or not raw_bundle:
                continue
            # Manifests may have been authored on Windows or POSIX; normalise
            # separators before resolving against the manifest directory.
            bundle = Path(raw_bundle.replace("\\", "/"))
            if not bundle.is_absolute():
                bundle = (profile.manifest_path.parent / bundle).resolve()
            if bundle.is_dir():
                index[(profile.profile_id, match_id)] = bundle
    return index
