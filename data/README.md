# `data/` 目录说明

## 目录结构

```
data/
├── raw/          原始比赛包（.rar / .dem），本地，不提交
├── processed/    规范化逐 tick bundle（CSV），本地，不提交
├── series/       team-map 聚合 profile，可提交
├── showcase/     公开演示 bundle（轻量），可提交
├── catalog/      本地地图索引，可能含绝对路径，不提交
├── registry/     本地比赛注册表，可能含绝对路径，不提交
├── intake-seeds/ 下载工作清单，本地，不提交
├── map_assets/   雷达底图（PNG）与坐标参数，可提交
```

## 各目录作用

### `raw/` — 原始 Demo（本地，~48 GB）

存放从 HLTV 等来源下载的 `.dem` 和 `.rar` 整场包。**不随 Git 提交**。通过 `scripts/import_demo.py` 或 `scripts/import_registry_corpus.py` 解析后生成规范化 bundle。

### `processed/` — 规范化 bundle（本地，~19 GB）

每场每张地图的逐 tick 解析结果，包括回合、击杀、位置、道具、伤害、经济快照和装备事件的 CSV 文件及校验元数据。**不随 Git 提交**。

每个 bundle 包含：

- `metadata.json` — 队伍、地图、导入状态与校验信息
- `rounds.csv` / `kills.csv` / `positions.csv` / `grenades.csv` — 核心游戏事件
- `damages.csv` / `bomb_events.csv` — 伤害与炸弹事件
- `economy_snapshots.csv` / `loadout_events.csv` — 经济与装备时间线

### `series/` — team-map 聚合 profile（可提交）

轻量分析产物，不包含逐 tick 数据：

```
data/series/
  iem-cologne-2026-{team}-{map}.json          # manifest
  iem-cologne-2026-{team}-{map}/              # 三件套目录
    series_metadata.json                      # 元数据
    precontact_opening_samples.csv             # 接触前样本
    precontact_opening_profile.csv             # 聚合 profile
```

这些文件体积小（每 profile 几十 KB），是公开仓库的核心分析成果。

### `showcase/` — 公开演示 bundle（可提交）

包含一个真实比赛的轻量公开演示（FURIA vs Falcons · Mirage · 21 回合），位置轨迹降采样至 8 Hz 并 GZip 压缩，所有事件表完整保留。运行 `scripts/build_showcase_bundle.py` 可重新生成。

- FURIA vs Falcons 完整击杀、道具、伤害、炸弹、经济和装备事件
- OB 式装备 HUD 可用
- 不含 64 tick/s 原始轨迹和 `data/processed/` 中其他 134 个 bundle
- 详细说明见 `showcase/README.md`

### `catalog/`、`registry/` 与 `intake-seeds/`（本地，不提交）

- `catalog/` — 通过 `scripts/catalog_match_archives.py` 生成的地图索引
- `registry/` — 比赛注册表，记录 match_id、队伍、阶段与文件成员
- `intake-seeds/` — 下载和导入阶段使用的来源页清单

这些文件可能包含当前电脑的 `D:\...` 绝对路径。它们对本地增量导入有用，但默认由 `.gitignore` 排除；如未来要公开，应先生成去除本机路径的单独 sanitized 版本。

### `map_assets/` — 雷达底图（可提交）

运行播放器必需。包含 7 张比赛地图的雷达 PNG（Ancient、Anubis、Dust2、Inferno、Mirage、Nuke、Overpass）以及 `map-data.json` 坐标参数。地图辅助图（如 Nuke 下层）也在此目录。

当前资源来自 Awpy artifact 工作流并包含 CS2 游戏图像。Awpy 代码采用 MIT License，但底图所含游戏素材的权利边界并不因此自动改变；正式公开前仍需确认再分发方式。

## 新用户如何构建本地数据

公开仓库不包含 `raw/` 和 `processed/`。新用户需：

1. 获取合法的 CS2 Demo 文件（如通过 HLTV 下载）
2. 运行导入器：

```powershell
python scripts/import_demo.py path/to/your.dem --output data/processed/your-bundle
```

3. 生成 team-map profile：

```powershell
python scripts/materialize_corpus_research_profiles.py --processed-root data/processed/your-corpus --coverage data/series/your-corpus/coverage_summary.json --series-root data/series
```

## 不推荐的做法

- **不要**用 Git LFS 存储 `raw/` 或 `processed/`。67 GB 的比赛语料不应通过 Git 分发。
- **不要**将 GitHub 当作对象存储。Demo 文件应通过赛事方或 HLTV 等渠道获取。
