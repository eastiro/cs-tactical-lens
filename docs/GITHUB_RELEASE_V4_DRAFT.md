# Release Title

CS Tactical Lens v4.0.0 — Evidence-led CS2 Tactical Analysis

# Tag

v4.0.0

# Release Body

## 一句话定位

把职业 CS2 比赛 Demo 转化为可审计的跨队伍、跨地图接触前结构比较工作台。所有结论都可追溯到具体比赛回合的雷达地图、选手轨迹和装备 HUD 证据。

## V4 核心能力

- **Research Workspace（研究工作台）**：选择两支队伍和一张地图，在统一的经济观察口径下并排查看双方的接触前站位分布与重复结构。样本覆盖量以 standard（≥5 场）、exploratory（3–4 场）、insufficient（<3 场）分级明示。
- **经济感知观察窗口**：全起 20 秒、半起 12 秒、手枪/刚枪/Eco 15 秒；未知类型回退 20 秒。仅提取首次实际交火前的样本，排除交火后受局势干扰的站位。
- **证据回放**：每项发现可一键跳回对应回合的雷达底图回放，包含击杀位置、道具轨迹与 OB 式装备 HUD。手动回放与研究证据回放两种来源互斥，不会串台。
- **公开轻量 Showcase**：仓库克隆后无需 67 GB 本地语料，点击"回放→加载公开 Showcase"即可体验 Furia vs Falcons（Mirage，21 回合，8 Hz 位置降采样）的完整回放流程。

## 验证与规模

| 项目 | 数值 |
|------|------|
| 已验证 Demo bundle | **135**（0 导入失败） |
| team-map research profile | **117** |
| 可用比赛地图 | 7（Ancient、Anubis、Dust2、Inferno、Mirage、Nuke、Overpass） |
| 公开 Showcase | **2.78 MB**（21 回合，8 Hz 位置降采样） |
| 公共提交 | 761 文件 / ≈8.16 MB |
| 全量测试 | **350 passed** |
| V4 发布审计 | **20/20 checks passed** |
| Showcase 专项测试 | **32 passed** |

## 快速体验

```powershell
git clone https://github.com/eastiro/cs-tactical-lens.git
cd cs-tactical-lens
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

启动后在页面中点击**回放 → 加载公开 Showcase** 即可立刻体验回放交互（无需任何本地 Demo 数据）。

如需构建自己的分析语料，需自行合法获取 CS2 Demo 文件并按 `scripts/` 中的导入流程处理。

## 数据与许可证边界

- 完整本地语料（`data/raw/` + `data/processed/` 约 67 GB）**不随仓库分发**。
- 源代码采用 **MIT License**。
- `data/map_assets/` 中的雷达/游戏衍生素材**不属于** MIT License，相关权利仍归 Valve Corporation 或其他相应权利人。详见 `THIRD_PARTY_NOTICES.md`。
- 本工具与 **Valve Corporation、赛事主办方、HLTV.org 无任何隶属或官方认可关系**。

## 已知限制

- 结论为描述性证据，**不声称恢复战术意图**，不做胜负预测。
- team-map 样本不足时只展示探索性结果并明确标注覆盖层级。
- 完整 corpus 目前来自单一赛事周期（IEM Cologne Major 2026）；跨赛事与跨阵容泛化需要继续验证。
- 中文区域词典目前仅完成 Mirage，其余 6 张比赛地图回退至区域级分组。

## AI 辅助开发

AI 编程工具辅助完成了大部分代码实现、测试脚本和文档初稿。作者负责产品方向、CS 领域判断、无效指标剔除、数据校验和最终验收。

---

## English Summary

CS Tactical Lens v4.0.0 transforms professional CS2 demo recordings into an auditable, cross-team pre-contact structure comparison workbench. It connects every tactical observation back to round-level radar replay with equipment HUD.

The current corpus contains 135 validated map bundles organized into 117 team-map research profiles across 7 competitive maps. A 2.78 MB public showcase (Furia vs Falcons, Mirage, 21 rounds, 8 Hz position sampling) lets anyone experience the full replay pipeline without downloading 67 GB of local data. The system is verified by 350 automated tests, a 20/20 release audit, and 32 showcase-specific tests.

Source code is MIT Licensed; game-derived radar assets are not covered by the MIT License. This project is not affiliated with Valve Corporation, tournament organizers, or HLTV.org.
