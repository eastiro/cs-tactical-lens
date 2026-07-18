# CS Tactical Lens: A Reproducible Pre-Contact Structure Analysis Workbench for CS2 Demo Data

## Abstract

CS Tactical Lens is a research-oriented personal project that builds an auditable analysis pipeline for professional **Counter-Strike 2** (CS2) match data. Its central design choice is to connect every displayed summary to concrete demo evidence at round, radar-map, and player-track granularity.

The current local corpus contains 135 validated map bundles and produces 117 team-map research profiles spanning 7 competitive maps. Each profile aggregates pre-contact positioning data across multiple matches for the same team on the same map, using economy-aware observation windows (12–20 s depending on buy category). A public showcase bundle (2.78 MB) demonstrates the replay pipeline without requiring the complete 67 GB local corpus. The system is verified by 350 automated tests and a 20/20 release audit.

The workbench explicitly stops short of tactical intent inference, win prediction, or claims about a team's "default" strategies. It provides descriptive, auditable evidence of where players position themselves before first contact — nothing more, nothing less.

---

## Problem and Motivation

Professional CS2 demos contain rich positional, economic, and event data, but extracting meaningful comparative insights across multiple matches is technically challenging:

- **Demo parsing requires a controlled data contract.** Raw demo files require specialized parsers such as Awpy, while parser or game-format changes can alter the resulting schema.
- **Single-match descriptions have limited scope.** A single match is influenced by opponent style, map side, and match-specific context. Aggregating multiple matches does not remove those effects, but makes repeated observations and sample coverage visible.
- **Aggregate outputs are difficult to audit without evidence links.** When a summary is not connected to its underlying round and game state, a reader cannot independently verify whether a claimed tendency reflects pre-contact positioning or later events.
- **The project needs an explicit unit of analysis.** Rather than claiming a universal community standard, this project defines one operational unit—team × map × pre-contact sample—and applies it consistently.

This project addresses these needs by defining a reproducible unit of analysis—the **team-map pre-contact profile**—and demonstrating an inspectable pipeline from raw demo to auditable comparative evidence, prepared for public release.

---

## Research Questions

1. **Pre-contact positioning:** How do professional CS2 teams distribute their players across map zones (A, B, MID, spawn) during the first 12–20 seconds of a round, before any opposing damage occurs?
2. **Economy-state sensitivity:** How does team positioning vary across different economy states (full-buy, half-buy, force-buy, eco, pistol)?
3. **Cross-team comparison:** How can two teams be compared under the same map, side, economy label, and observation rule while keeping opponent-specific effects visible as a limitation?
4. **Sample transparency:** How should match coverage be shown so that readers do not mistake small-sample descriptions for stable population-level patterns? (The project uses ≥5 matches as the "standard" tier—an engineering heuristic, not a statistical power analysis.)

---

## Data and Unit of Analysis

**Source data:** 135 normalized demo bundles from IEM Cologne Major 2026, covering 7 competitive maps (Ancient, Anubis, Dust2, Inferno, Mirage, Nuke, Overpass). Each bundle contains round-level outcomes, kill events, damage events, player positions at 64 ticks/s, grenade trajectories, economy snapshots at freeze-end, and compressed loadout-change events.

**Unit of analysis:** The **team-map profile** — all available matches for one team on one map. This is deliberately not a "team profile" (across all maps) or a "match profile" (one match only). Comparing the same team on the same map controls for map-specific spatial conventions.

**Coverage tiers:**

| Tier | Matches | Label |
|------|---------|-------|
| Standard | ≥5 | Sufficient for descriptive pattern observation |
| Exploratory | 3–4 | Limited samples; patterns are tentative |
| Insufficient | <3 | Visible with a sample-warning label; not adequate for a general conclusion |

The ≥5 threshold is an engineering heuristic, not a statistical significance boundary.

---

## Methodology

### Pre-Contact Extraction

The core methodological choice is to analyze **only the period before first opposing-team contact** (damage or kill). This avoids conflating a team's round-start setup with their reaction to opponent action.

For each eligible round:
1. Determine the economy label via deterministic rules applied to freeze-end inventory, equipment value, armor, and starting balance.
2. Select an economy-appropriate observation window: full-buy 20 s, half-buy 12 s, pistol/force/eco 15 s. Unknown classifications fall back to 20 s.
3. Extract each surviving player's position at the observation deadline, grouped into zones (A, B, MID, spawn).
4. Record the formation (e.g., "A2·B2·MID1·spawn0").
5. Classify the sample as eligible only if the observation window completes before first opposing contact.

### No Machine Learning

All classifications (economy state, formation grouping, contact detection) use deterministic rules operating on parsed game-state fields. There are no trained models, no embeddings, and no probabilistic inferences. This design choice ensures full auditability: every classification can be traced to specific game-state features.

### Cross-Team Comparison

Two teams are compared using the same map, side, economy label, and observation contract. The current corpus comes from one event, but the teams do not necessarily share the same opponents; this comparison therefore standardizes the measurement rule without controlling away opponent effects. It is limited to pre-contact structures and explicitly avoids:
- Round win/loss prediction
- Tactical intent attribution ("Team A is running a default strategy")
- Performance quality scoring

---

## System Architecture / Evidence Pipeline

```
Match Demo (.dem / .rar)
    │
    ▼
  Normalized Bundle (CSV: rounds, kills, positions, grenades,
  damages, bomb events, economy snapshots, loadout events)
    │
    ▼
  Import Results (135 validated, 0 errors)
    │
    ▼
  Coverage Summary (coverage tiers per team-map)
    │
    ▼
  Team-Map Profile (manifest + 3 artifacts)
    ├── series_metadata.json
    ├── precontact_opening_samples.csv
    └── precontact_opening_profile.csv
    │
    ▼
  Research Workspace → Cross-Team Comparison → Evidence Replay
```

Each stage produces auditable intermediate artifacts. The profile artifacts are lightweight (tens of KB per profile) and can be distributed with the public repository.

---

## Evaluation and Verification

The system is verified at three levels:

1. **Unit and integration tests (350 passed).** Cover demo parsing, coordinate projection, round timeline rendering, tactical findings, loadout timeline, economy classification, replay state machine, cross-map UI contract, corpus integrity, and showcase bundle loading.

2. **Release audit (20/20 checks passed).** An independent audit script (`scripts/audit_v4_release.py`) verifies:
   - 135 parsed bundles, 0 import errors
   - 117 corpus profiles all discoverable by the catalog API
   - Bundle map/team consistency across all match entries
   - Coverage tier consistency with match counts
   - Replay contract (7 maps readable, required columns present, loadout HUD functional, radar projection works)

3. **Source bundle integrity.** The public showcase bundle (Furia vs Falcons, Mirage, 21 rounds) preserves full event tables and downsamples positions from 1,482,670 to 185,740 rows (8 Hz, approximately 8x row reduction); GZip reduces the position file by roughly 45x. Source bundle SHA-256 hashes are unchanged after export.

---

## What the Current Results Can and Cannot Support

| Supported | Not Supported |
|-----------|---------------|
| Descriptive pre-contact positioning patterns for a team on one map | Claims about a team's "default strategy" or tactical intent |
| Economy-state-stratified spatial distributions | Win/loss prediction or round outcome attribution |
| Cross-team comparison under the same map and measurement contract | Causal claims that differences are produced by team preference rather than opponents or context |
| Reproducible, auditable evidence chain from demo to finding | Statistical significance or population-level inference |
| Coverage-tier-appropriate sample transparency | Generalization beyond available match count |

---

## Threats to Validity / Limitations

1. **Ecological validity.** Pre-contact structure is a thin slice of a complete round. The 12–20 s observation window captures initial setup but not mid-round adaptations, utility usage, or clutch situations.
2. **Opponent confound.** Observed positioning reflects not only the target team but also its opponent, available information, utility, sound cues, prior-round adaptation, and match context. Applying one measurement contract makes outputs comparable, but the current data does not provide a matched opponent pool and therefore does not remove this confound.
3. **Event-specific context.** All data comes from a single tournament (IEM Cologne Major 2026). Results may not generalize to other events, roster iterations, or game patches.
4. **Map coverage.** The Chinese regional dictionary and detailed tactical analysis are only available for Mirage. Non-Mirage maps fall back to zone-level (A/B/MID/OTHER) grouping without sub-region labels.
5. **Sample size.** "Standard" tier (≥5 matches) is an engineering convenience, not a statistically validated threshold. Once samples are split by side and economy state—and early-contact rounds are excluded—the usable count can remain small even across five matches.
6. **Parser dependency.** The pipeline relies on Awpy for demo parsing. Parser updates or changes in CS2's demo format could require re-validation.

---

## Reproducibility and Public Showcase

The codebase and lightweight Showcase are prepared for public GitHub release. The full 67 GB corpus of raw demos and processed bundles is **not distributed** with the repository due to size and redistribution constraints. The source code is released under the MIT License; game-derived assets remain outside that license as documented in `THIRD_PARTY_NOTICES.md`.

A **public showcase bundle** (`data/showcase/furia-falcons-mirage/`, 2.78 MB) allows any user to experience the full replay pipeline without downloading the corpus:

```bash
pip install -r requirements.txt
streamlit run app.py  # Click "Replay" → "Load Public Showcase"
```

The showcase contains all event tables from a real match (Furia vs Falcons, Mirage, 21 rounds) with positions downsampled to 8 Hz. It demonstrates radar replay, utility animations, and the OB-style equipment HUD. It does **not** enter cross-team comparison conclusions.

Users who wish to build their own corpus can use the provided import scripts with legitimately obtained CS2 demo files.

---

## AI-Assisted Development Disclosure

This project was developed with extensive use of AI-assisted programming tools. The division of labor is:

- **Human author:** Product conception, CS domain expertise, iterative identification of meaningless metrics, definition of stop conditions, demo data preparation, visual inspection of results, evidence boundary decisions, and final direction.
- **AI tools:** Majority of code implementation, test script generation, data processing scripts, UI iteration, and documentation drafts.

Collaboration between human and AI agents followed a structured workflow using task specifications, code review, regression testing, and final acceptance verification. The approach is best described as **AI-assisted engineering with iterative human validation**.

---

## Future Work

- Automated demo acquisition and incremental parsing pipeline
- Object storage for corpus management
- Roster-period filtering (comparing only matches with the same player lineup)
- Extended Chinese regional dictionaries beyond Mirage
- Configurable economy observation windows
- Community contributions for additional map dictionaries

---

## Conclusion

CS Tactical Lens demonstrates a working research prototype for auditable pre-contact structure analysis of professional CS2 matches. By constraining its outputs to descriptive evidence and explicitly marking coverage limitations, it provides a concrete basis for evidence-led tactical discussion without claiming to recover team intent. The analysis runtime uses inspectable Python components, and the MIT-licensed codebase is testable and prepared for public inspection with its game-asset boundary documented separately.

---

*Disclaimer: This project is not affiliated with Valve Corporation, tournament organizers, or HLTV.org. Match demo files, game assets, and team names are the property of their respective owners.*
