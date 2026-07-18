# CS Tactical Lens V4 — Release Notes

> 草稿，准备用于 GitHub Release `v4.0.0`。不含正式发布日期、下载链接或已发布仓库 URL。

---

## English Summary

**CS Tactical Lens V4** is a research-oriented personal project that transforms professional CS2 demo recordings into an auditable, cross-team pre-contact structure comparison workbench. It connects every tactical observation back to the original match replay at round, radar-map, and equipment-HUD granularity.

Key capabilities: Research Workspace for team-map comparison, economy-aware observation windows (12–20 s), evidence replay with OB-style HUD, and a public 2.78 MB showcase bundle for immediate hands-on experience.

**Data:** 135 validated map bundles → 117 team-map profiles → 7 competitive maps.
**Verification:** 350 automated tests · 20/20 release audit.
**Limitations:** Pre-contact structure only; Mirage Chinese dictionary only; no tactical intent inference or win prediction.

---

## V4 核心定位

CS Tactical Lens V4 是一个研究型个人项目，定位为**可复核的多场接触前结构比较工作台**。它不是商业分析平台，不是 AI 战术识别系统，也不是已发表科研成果。所有结论都可追溯到具体回合的雷达地图与选手轨迹证据。

## 功能

### 研究工作台（Research Workspace）

- 跨队伍、跨地图的多场接触前结构比较
- 数据单位：team × map（一支队伍 + 一张地图 + 多场比赛）
- 覆盖层级：standard（≥5 场）、exploratory（3–4 场）、insufficient（<3 场）
- 每项发现可跳回具体回合的雷达证据回放

### 经济分类

- 确定性规则，不使用机器学习
- 观察秒数：全起 20s、半起 12s、手枪/刚枪/Eco 15s、未知回退 20s
- 置信度与判定原因随数据输出

### 证据回放 & 手动回放

- 两种来源互斥，不会串台
- 包含雷达地图、选手轨迹、击杀位置、道具动画
- OB 式装备 HUD（需 bundle 含 `loadout_events.csv`）

### 战术模式（Mirage）

- 中文区域词典与开局结构划分已完成
- 非 Mirage 地图显示边界提示并安全停止
- 非 Mirage 的回放和复盘报告仍正常可用

## 数据规模

| 项目 | 数值 |
|------|------|
| 已验证 Demo bundle | **135**（0 导入失败） |
| corpus research profile | **117** |
| 可用比赛地图 | 7（Ancient / Anubis / Dust2 / Inferno / Mirage / Nuke / Overpass） |
| 公开 Showcase | 2.78 MB（Furia vs Falcons · Mirage · 21 回合 · 8 Hz 位置降采样） |

## 验证

- 全量测试：**350 passed**
- 发布审计：**20/20 checks passed**（`scripts/audit_v4_release.py`）
- Showcase 专项测试：**32 passed**

## 安装与启动

```powershell
pip install -r requirements.txt
streamlit run app.py --server.port 8508
```

无需完整语料：启动后点击"回放"→"加载公开 Showcase" 即可体验。

## 数据边界

完整语料（`data/raw/` + `data/processed/` 约 67 GB）不随仓库分发。公开仓库包含源代码、轻量 team-map profile（`data/series/`）和雷达地图资产（`data/map_assets/`）。新用户需自行准备合法的 CS2 Demo 文件并运行导入脚本。

## 无法支持的结论

- ❌ "战队默认战术"或战术意图推断
- ❌ 胜负预测或回合结果归因
- ❌ 跨赛事或跨阵容期比较（语料来自单一赛事）
- ❌ 统计显著性结论（≥5 场为工程阈值，非统计标准）

## AI 辅助开发

本项目使用 AI 编程工具辅助完成大部分代码实现、测试和文档初稿。作者负责产品方向、CS 领域判断、数据检查和最终验收。协作方式为 "AI 辅助工程与人工迭代验证"。

## 已知限制

- 非 Mirage 地图无中文子区域标签
- 接触前结构只占完整回合的薄切片
- 所有数据来自 IEM Cologne Major 2026，跨赛事泛化需额外验证
- 依赖 Awpy 进行 Demo 解析，解析器更新可能需要重新校验

## 许可证

项目源代码采用 MIT License。`data/map_assets/` 中的雷达/游戏相关图像不属于该代码许可证，详见 `THIRD_PARTY_NOTICES.md`。
