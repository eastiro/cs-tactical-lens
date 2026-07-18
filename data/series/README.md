# 同队同图多场数据

这里存放的不是“所有 Mirage 比赛”的混合样本，而是一支固定队伍在一张固定地图上的多场已解析 Demo。

## 为什么这样组织

单场的下包点、首杀后站位和回合末路线是双方中期博弈共同造成的结果，不能倒推成队伍偏好。

多场分析只先提取**首次实际交火前**的开局位置。它是研究默认结构的候选证据，不自动判断既定战术。

## 清单格式

以 `falcons-mirage.example.json` 复制出自己的清单。每条 `bundle` 指向已经由 `scripts/import_demo.py` 解析完成的目录。

一份清单只允许：

- 一支目标队伍；
- 一张地图；
- 多个不同对手或不同赛事的比赛。

建议先收集至少 6 场同图职业比赛。当前 Falcons Mirage 样本限定为 2026-05-09 起的 karrigan 阵容（karrigan、NiKo、TeSeS、m0NESY、kyousuke）；不要把换阵前比赛混入。当前还没有验证过的冻结结束经济快照，所以输出会明确标记 `economy_scope = unclassified`；不得把 eco、强起和长枪局混在一起称为完整默认习惯。

## 生成接触前样本

```powershell
python scripts\build_team_map_series.py data\series\falcons-mirage.json --output data\series\falcons-mirage
```

输出包括：

- `precontact_opening_samples.csv`：每回合在指定秒数的接触前样本；首次交火早于采样点的回合会被明确排除。
- `precontact_opening_profile.csv`：相同人数结构的计数与可追溯回合。
- `series_metadata.json`：样本量、排除边界和当前经济分类限制。
