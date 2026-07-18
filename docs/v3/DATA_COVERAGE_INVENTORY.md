# 本地 Demo 数据资产盘点（V3.4）

> 盘点日期：2026-07-17
> 范围：`data/raw`、`data/processed`、`data/catalog`、`data/series`

## 盘点的目录

| 目录 | 存在 | 内容 |
|------|------|------|
| `data/raw/` | ✅ | 原始 Demo 归档（.rar / .dem） |
| `data/raw/falcons-mirage/` | ✅ | Falcons Mirage 及相关对手的原始包（11 个文件） |
| `data/processed/` | ✅ | 已解析 normalized bundle |
| `data/catalog/` | ✅ | 比赛索引、队伍-地图分类 |
| `data/series/` | ✅ | 构建完成的接触前样本 series |

## 战队 × 地图 × 阵容期总表

| 战队 | 地图 | 阵容期 | 原始资产 | 已解析 bundle | 完整 series | 当前状态 | 距离可比较缺口 |
|------|------|--------|---------|-------------|------------|---------|--------------|
| **Team Falcons** | de_mirage | karrigan 阵容（2026-05 起） | 11 个原始包（含 .dem + .rar） | 10 场完整 bundle | ✅ 10 场 / 129 有效样本 | **可比较** | 无 |
| **Team Spirit** | de_mirage | zont1x/donk/sh1ro/tN1R/magixx（2026 稳定期） | 9 个原始 .rar（全部已解析） | 9 场 bundle（1 场 p1/p2 分段已排除） | ✅ 8 场 / 109 有效样本 | **可比较** | 无 |
| **Team Falcons** | de_ancient | karrigan 阵容 | 部分原始包（在 raw 中） | 待构建 | ❌ 无 series | 仅 catalog 索引 | 需解析 + 构建 series |
| **Team Falcons** | de_anubis | karrigan 阵容 | 部分原始包 | 待构建 | ❌ 无 series | 仅 catalog 索引 | 需解析 + 构建 series |
| **Team Falcons** | de_dust2 | karrigan 阵容 | 部分原始包 | 待构建 | ❌ 无 series | 仅 catalog 索引 | 需解析 + 构建 series |
| **Team Falcons** | de_inferno | karrigan 阵容 | 部分原始包 | 待构建 | ❌ 无 series | 仅 catalog 索引 | 需解析 + 构建 series |
| **Team Falcons** | de_nuke | karrigan 阵容 | 部分原始包 | 待构建 | ❌ 无 series | 仅 catalog 索引 | 需解析 + 构建 series |
| FURIA | de_mirage | 未知（仅 V1 单场 demo） | 1 个 .dem | 1 场 bundle（无 economy/loadout 富化） | ❌ 无 series | **V1 遗留默认项** | 不足 5 场，且无阵容期确认 |

> "完整 series"条件：同时存在 manifest（.json）、metadata、precontact_opening_samples.csv、precontact_opening_profile.csv。

## 可立即比较的组合

| 战队 A | 战队 B | 地图 | 共同对手场次 |
|--------|--------|------|------------|
| **Falcons**（10 场） | **Spirit**（8 场） | **de_mirage** | 2 场直接交手（PGL Astana + IEM Cologne），但各自另有其他对手 |

两队均≥5 场 Mirage、同阵容期已确认、经济分类和事件流均已富化。**这是当前唯一可进行跨队比较的组合。**

## 完整 series 明细

### Falcons · Mirage · karrigan 阵容（10 场）

| # | 赛事 | vs | 日期 | bundle | 经济快照 | 事件流 |
|---|------|----|------|--------|---------|-------|
| 1 | PGL Astana 2026 | 9z | 2026-05-10 | ✅ | ✅ | ✅ |
| 2 | PGL Astana 2026 | The MongolZ | 2026-05-12 | ✅ | ✅ | ✅ |
| 3 | PGL Astana 2026 | FURIA | 2026-05-15 | ✅ | ✅ | ✅ |
| 4 | PGL Astana 2026 | Spirit | 2026-05-17 | ✅ | ✅ | ✅ |
| 5 | CS Asia Championships 2026 | MOUZ | 2026-05-23 | ✅ | ✅ | ✅ |
| 6 | CS Asia Championships 2026 | Legacy | 2026-05-24 | ✅ | ✅ | ✅ |
| 7 | IEM Cologne Major 2026 | Monte | 2026-06-13 | ✅ | ✅ | ✅ |
| 8 | IEM Cologne Major 2026 | Natus Vincere | 2026-06-14 | ✅ | ✅ | ✅ |
| 9 | IEM Cologne Major 2026 | Spirit | 2026-06-20 | ✅ | ✅ | ✅ |
| 10 | IEM Cologne Major 2026 | FURIA | 2026-06-21 | ✅ | ✅ | ✅ |

- 有效样本：129
- 经济分布：full_buy 72 / pistol 19 / half_buy 16 / force_buy 10 / eco 5 / unknown 4 / mixed 3

### Spirit · Mirage · 稳定阵容期（8 场）

| # | 赛事 | vs | 日期 | bundle | 经济快照 | 事件流 |
|---|------|----|------|--------|---------|-------|
| 1 | BLAST Bounty 2026 S1 Finals | PARIVISION | 2026-01-23 | ✅ | ✅ | ✅ |
| 2 | IEM Rio 2026 | G2 | 2026-04-15 | ✅ | ✅ | ✅ |
| 3 | IEM Rio 2026 | Falcons | 2026-04-18 | ✅ | ✅ | ✅ |
| 4 | IEM Rio 2026 | MOUZ | 2026-04-18 | ✅ | ✅ | ✅ |
| 5 | IEM Rio 2026 | Vitality | 2026-04-20 | ✅ | ✅ | ✅ |
| 6 | PGL Astana 2026 | Falcons | 2026-05-17 | ✅ | ✅ | ✅ |
| 7 | IEM Cologne Major 2026 | 9z | 2026-06-07 | ✅ | ✅ | ✅ |
| 8 | IEM Cologne Major 2026 | 9z (stage 1) | 2026-06-13 | ✅ | ✅ | ✅ |

- 有效样本：109
- 经济分布：full_buy 66 / pistol 15 / force_buy 13 / half_buy 12 / eco 2 / unknown 1
- 排除 1 场：IEM Cologne Major 2026 stage 2 vs 9z（p1/p2 分段包，不构成完整比赛）

## 富化状态

| 富化类型 | Falcons（10 场） | Spirit（9 场） | V1 默认（1 场） |
|----------|-----------------|---------------|----------------|
| `economy_snapshots.csv` | ✅ 全部 10 场 | ✅ 全部 9 场 | ❌ |
| `loadout_events.csv` | ✅ 全部 10 场 | ✅ 全部 9 场 | ❌ |

## 原始 Demo 状态

- `data/raw/falcons-mirage/`：11 个文件，10 个 rar + 1 个 .dem（V1 单场）
  - 10 个 rar 全部已解析为 Falcons/Mirage 系列 bundle
  - 1 个 .dem（furia-vs-falcons-m1-mirage）为 V1 默认 Demo 的原始文件
- `data/raw/*.rar`：9 个 Spirit 相关 raw，全部已解析为 Spirit bundle（含 1 个分段包）
- **无未解析的 raw 资产**

## 建议

### 建议 1：补齐 Spirit 的另一张地图 series（优先度：中）

Spirit 的 catalog 包含 `de_mirage` 之外的多张地图索引（通过 Falcons catalog 的对手视角），但尚未作为 Spirit 主队的完整 series 构建。如果原料文件仍在本地 raw 目录中（以 Spirit 为对手散落在 Falcons 包里），可以尝试为 Spirit 构建第二张地图的 series。

**理由**：不依赖新 Demo 下载，完全复用已有已解析 bundle。

### 建议 2：为 Falcons 构建 Mirage 以外的系列（优先度：低）

Falcons catalog 已覆盖 6 张地图（ancient / anubis / dust2 / inferno / mirage / nuke），但只有 mirage 有完整 series。若目标是为 Falcons 提供多图比较能力，可从 catalog 中有足够场次的地图开始构建。

**理由**：catalog 已有索引，但未经验证是否满足 5 场门槛和阵容期一致性。

### 建议 3：不要以 V1 FURIA 默认 Demo 为基础构建 series（优先度：无需操作）

V1 默认 Demo 仅 1 场，无阵容期信息，无经济/事件富化。不应作为任何比较或 series 的数据来源。

**理由**：数据口径不足，且与当前 V3 产品方向（多场验证）不匹配。

---

> 本次盘点未修改任何生产文件。所有数据来源于 `data/` 下已有的文件系统结构。
