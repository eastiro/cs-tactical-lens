# Showcase Bundle

此目录包含一个**真实比赛的轻量公开演示 bundle**，用于在克隆仓库后无需完整语料即可体验回放交互。

## 数据来源

- **比赛**：FURIA vs Falcons（IEM Cologne Major 2026 季后赛）
- **地图**：de_mirage
- **回合数**：21 回合
- **源位置轨迹**：64 tick/s（完整本地数据）
- **演示轨迹**：8 Hz 降采样（每个选手每回合首尾样本 + 每 8 个源 tick 保留一个）

## 包含

- 全部 21 回合的击杀、道具、伤害、炸弹事件
- 完整经济快照（`economy_snapshots.csv`）
- 完整装备事件时间线（`loadout_events.csv`）— 可激活 OB 式装备 HUD
- 位置轨迹经 8 Hz 降采样后以 GZip 压缩（`positions.csv.gz`）
- 元数据已脱敏，不含本机绝对路径

## 不包含

- 原始 `.dem` 文件
- 完整 64 tick/s 位置轨迹
- `data/processed/` 中的其他 134 个 bundle
- 不属于 FURIA vs Falcons 的任何比赛数据

## 使用方式

启动分析台后，在**回放**页面点击"加载公开 Showcase"按钮即可。

## 许可说明

此演示包含真实比赛事件数据。比赛 Demo 文件、游戏素材和战队名称的权利归各自权利人所有。此数据不应用于训练模型或重新分发原始 Demo。

## 重新生成

```powershell
python scripts/build_showcase_bundle.py ^
  --source data/processed/iem-cologne-major-2026-corpus/2395002/de_mirage ^
  --output data/showcase/furia-falcons-mirage
```
