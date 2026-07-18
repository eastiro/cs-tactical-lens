# V4 发布前底层总验收报告

> 生成时间：2026-07-18T08:52:50.669672+00:00

**20 / 20 检查通过（失败 0 项）**

## A. Corpus 与 Profile 完整性

### ✅ A1: import_results: parsed_and_validated=135, error=0

- **状态**: 通过
- **详情**: expected PV=135 err=0, got PV=135 err=0

### ✅ A2: Discoverable corpus profiles: 117 (total 121, handcrafted 4)

- **状态**: 通过
- **详情**: expected 117 corpus profiles, got 117

### ✅ A3: Manifest team/map/match_count matches series_metadata

- **状态**: 通过
- **详情**: 0 mismatches

### ✅ A4: Bundle exists and map_name matches profile

- **状态**: 通过
- **详情**: 0 missing, 0 map mismatch, 0 total

### ✅ A5: Profile team is in bundle team_a/team_b

- **状态**: 通过
- **详情**: 0 violations

### ✅ A6: No duplicate match IDs within a profile

- **状态**: 通过
- **详情**: 0 duplicate cases

### ✅ A7: Coverage tier consistent with match_count (5+ standard, 3-4 exploratory, <3 insufficient)

- **状态**: 通过
- **详情**: 0 mismatches

### ✅ A8: No empty manifests, empty bundle paths, or incomplete profiles among discovered

- **状态**: 通过
- **详情**: 0 issues

## B. 回放底层契约

### ✅ B1: All 7 competitive maps have a readable bundle

- **状态**: 通过
- **详情**: missing maps: [], load failures: []

### ✅ B2: Required columns present in rounds/positions/kills/grenades

- **状态**: 通过
- **详情**: 0 column issues

### ✅ B3: loadout_payload_for_round works on bundles with loadout_events

- **状态**: 通过
- **详情**: 0 failures

### ✅ B4: Loadout events sorted by seconds/tick, inventory is list

- **状态**: 通过
- **详情**: 0 issues

### ✅ B5: Missing loadout returns clean empty structure

- **状态**: 通过
- **详情**: ok

### ✅ B6: Radar params and 7 competitive map PNGs exist

- **状态**: 通过
- **详情**: 0 issues

### ✅ B7: project_frame() works on each map without crashing

- **状态**: 通过
- **详情**: 0 failures

## C. 构建和重跑安全

### ✅ C1: Dry-run all tiers plans all profiles

- **状态**: 通过
- **详情**: exit=0, planned_lines=118

### ✅ C2: Results CSV status matches actual disk state

- **状态**: 通过
- **详情**: 0 mismatches

### ✅ C3: No systematic cascading profile corruption

- **状态**: 通过
- **详情**: 0/117 incomplete profiles

### ✅ C4: Results CSV has 117 entries: {'skipped': 117}

- **状态**: 通过
- **详情**: ok, statuses: {'skipped': 117}

### ✅ C5: Corpus discovery does not depend on old handcrafted profiles

- **状态**: 通过
- **详情**: corpus=117, handcrafted={'spirit-mirage-2026-stable', 'falcons-mirage-2026-karrigan', 'falcons-dust2-2026-karrigan', 'spirit-dust2-2026-stable'}

---

*审计脚本只读运行，未修改任何数据或代码。*
