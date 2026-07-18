# CS Tactical Lens

一个把真实 CS2 比赛 Demo 转化为**可复核的多场接触前结构比较工作台**的个人数据分析项目。支持跨队伍、跨地图的站位证据提取与回放，所有结论都能回到实际比赛回合、雷达地图与 OB 式装备 HUD 逐秒核对。

V4 作品集版本已经完成：它不再是固定单场演示，而是一套经过 350 项本地测试验证的分析工作台。

> **代码许可证**：项目源代码采用 [MIT License](LICENSE)。
> **雷达/游戏素材**：不自动属于未来代码许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
> **研究说明**：参见 [English](docs/RESEARCH_NOTE.md) · [中文](docs/RESEARCH_NOTE_ZH.md)。

---

## V4 当前能力

### 研究工作台（Research Workspace）

跨队伍、跨地图的多场接触前结构比较。从已验证的 local corpus 中选择两支队伍和一张地图，即可并排查看双方在**首次实际交火前**的站位分布与重复结构。观察时刻按经济类型使用可解释规则：全起 20 秒、半起 12 秒，手枪/刚枪/Eco 15 秒；未知类型回退到 20 秒。

- 数据单位是 **team × map**（一支队伍 + 一张地图 + 多场比赛）
- 覆盖标签：**standard**（≥5 场）、**exploratory**（3–4 场）、**insufficient**（<3 场）
- 每项发现可跳回具体回合的雷达证据回放

### 经济分类

基于冻结结束装备快照的回合经济分级：`full_buy`、`half_buy`、`force_buy`、`eco`、`pistol`。分类由主武器、护甲、装备价值和冻结结束余额等字段上的确定性规则完成，不使用训练模型；置信度与判定原因随数据输出。无可靠装备快照的回合标注为 `unknown/unclassified`，不会冒充完整结论。

### 证据回放 & 手动回放

- **研究证据回放**：从比较证据行进入，锁定具体回合，加载原始 bundle 回放
- **手动回放**：从 profile → match 选择路径加载任意已验证比赛
- 两种来源互斥，不会串台
- 回放包含雷达地图、选手轨迹、击杀位置、道具动画

### OB 式装备 HUD

有 `loadout_events` 的 bundle 自动激活横向装备卡片（左侧 T 方、右侧 CT 方），显示每位选手的当前主武器、投掷物、护甲、装备价值与 freeze-end 余额。

### 战术模式（Mirage）

当前 Mirage 的中文区域词典与开局结构划分已完成。非 Mirage 地图显示边界提示并安全停止，不套用 Mirage 区域制造错误结论。非 Mirage 的回放和复盘报告仍正常可用。

### 刻意不做

- 不输出"默认战术""战队偏好"等无法从接触前站位直接证明的结论
- 不提供胜率模型、实时赔率或比赛预测
- 不使用 AI 自动识别战术
- 不把少量比赛包装成完整战队画像

---

## 产品工作流

```
原始比赛 Demo（.dem / .rar）
       ↓
  规范化 bundle（逐 tick 事件 CSV）
       ↓
  import_results.csv（135 已验证）
       ↓
  coverage_summary.json → 按场数分档（standard / exploratory / insufficient）
       ↓
  team-map research profile（manifest + 三件套）
       ↓
  研究工作台 → 跨队比较 → 证据行 → 回放核对
```

---

## 数据规模

| 项目 | 数值 |
|------|------|
| 已验证地图 Demo / bundle | **135**（0 导入失败） |
| corpus research profile | **117**（全部被 `discover_research_profiles()` 发现） |
| 可用比赛地图 | 7（Ancient、Anubis、Dust2、Inferno、Mirage、Nuke、Overpass） |
| 雷达底图 | 7 张 + 辅助图 |
| 全量测试 | **350 passed** |
| 发布审计 | **20/20 checks passed** |

---

## 页面与功能

| 页面 | 功能 |
|------|------|
| **研究工作台** | 选队伍 / 地图 / tier → 并排比较双方 0:20 开局结构 → 点击证据行跳转回放 |
| **回放** | 含雷达、轨迹、击杀、道具动画、装备 HUD 的回合级回放；连续播放或单帧模式 |
| **单场工具 → 战术模式** | 仅 Mirage：0:20 重复阵型、首杀转化、多回合位置观测 |
| **单场工具 → 复盘报告** | 下包终点、T 方首杀转化、首杀后重复重心、0:20 站位结构 |
| **单场工具 → 多场样本** | 同一队伍在多场比赛中的站位比较 |

---

## 快速开始

### 前提

- Python 3.12+
- 运行完整回放需要本地已解析的 Demo bundle（见下方"数据边界"）

### 无需完整语料快速体验

仓库包含一个**真实比赛的轻量公开演示**（FURIA vs Falcons · Mirage · 21 回合），位置轨迹降采样至 8 Hz 并压缩存储，全部事件表完整保留。

```powershell
# 启动后无需任何配置即可体验
python -m streamlit run app.py --server.port 8508
```

在浏览器中打开 `http://localhost:8508` → 点击**回放** → 点击 **"加载公开 Showcase"** 按钮。即可立即使用雷达回放、道具动画和 OB 式装备 HUD。

> 这是真实比赛的 8 Hz 轻量轨迹版本，用于快速体验回放交互。正式本地 V4 保留 64 tick/s 完整时基。Showcase 不进入跨队研究结论。

### 安装与启动

```powershell
cd cs-demo-analyzer
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8508
```

或双击项目根目录的 `打开分析台.cmd`。

浏览器访问 `http://localhost:8508`。

### 运行测试

`py_compile` 可在纯代码克隆中运行。完整测试和发布审计包含真实 corpus 契约，需要维护者本地未公开的 `data/processed/`；下列结果是 V4 发布时在完整本地语料上得到的，不代表 GitHub 克隆会自动下载比赛数据。

```powershell
# 纯代码编译检查
python -m py_compile app.py

# 维护者完整本地语料：全部测试
python -m pytest -q

# 维护者完整本地语料：发布审计
python scripts/audit_v4_release.py

# V4 回放状态机专项
python -m pytest -q tests/test_replay_state_machine.py
```

### 构建自己的 profile

```powershell
# 1. 导入 Demo
python scripts/import_demo.py path/to/your.dem --output data/processed/your-bundle

# 2. 生成 team-map 系列
python scripts/build_team_map_series.py data/series/your-team-map.json --output data/series/your-team-map
```

---

## 数据边界

完整本地语料（`data/raw/` ~48 GB + `data/processed/` ~19 GB）**不随仓库分发**。

公开仓库包含：

- 源代码（`app.py`、`src/`、`scripts/`、`tests/`）
- 轻量聚合 profile（`data/series/`）— team-map 层面的统计摘要，不含逐 tick 数据
- 地图雷达资产（`data/map_assets/*.png`）— 运行播放器必需
- 公开仓库不包含带本机绝对路径的 `data/registry/`、`data/catalog/` 和下载工作清单

`data/series/` 可用于阅读轻量聚合结果，但其中指向完整 bundle 的证据回放只有在本地补齐 `data/processed/` 后才能工作。新用户需自行准备合法的 CS2 Demo 文件并按导入流程生成本地数据。Git LFS **不**应用于存储 67 GB 比赛语料。

---

## 项目结构

```
app.py                     # Streamlit 主界面
src/
  awpy_adapter.py          # Awpy 数据规范化与校验
  map_geometry.py          # 游戏坐标 → 雷达坐标
  replay.py                # 回合快照、轨迹与事件
  round_timeline.py        # 单回合人数曲线与时间线
  tactics.py               # Mirage 中文区域与战术模式
  team_map_series.py       # 同队同图多场样本
  team_map_comparison.py   # 跨队比较
  loadout_timeline.py      # 装备事件时间线
  economy.py               # 经济分类
  analytics.py             # 报告指标
  schema.py                # 稳定表结构契约
scripts/
  import_demo.py           # 单 demo 导入
  catalog_match_archives.py# 整场包地图索引
  build_team_map_series.py # team-map profile 构建
  materialize_corpus_research_profiles.py # corpus 批量物化
  audit_v4_release.py      # 发布审计
data/
  series/                  # team-map 聚合 profile（可提交）
  map_assets/              # 雷达底图与坐标参数（可提交）
  registry/                # 本地注册表，含本机路径（不提交）
  catalog/                 # 本地地图索引，含本机路径（不提交）
  processed/               # 规范化 bundle（本地，不提交）
  raw/                     # 原始 Demo 与比赛包（本地，不提交）
tests/                     # 测试
docs/
  RESEARCH_NOTE.md         # 研究说明（英文）
  RESEARCH_NOTE_ZH.md      # 研究说明（中文）
  RELEASE_NOTES_V4.md      # V4 发布说明
  GITHUB_RELEASE_CHECKLIST.md  # 发布前检查清单
THIRD_PARTY_NOTICES.md     # 第三方声明与素材权利
reports/                   # 验收与审计报告
```

---

## V4 停止条件与 V5 方向

### V4 边界

- 数据源为本地已下载的 CS2 Demo，非实时流
- Mirage 中文区域词典已完成；其余 6 张比赛地图保留边界提示
- 比较只在相同地图和相同经济观察口径内进行；不同队伍样本量由 coverage tier 明示

### V5（生产化路线，非未修 Bug）

- 自动抓取与增量解析管道
- 对象存储管理本地语料
- 时间窗口支持（选阵容期而非全部混在一起）
- 更多地图的中文区域词典
- 可配置的经济观察秒数分层

---

## 免责声明

本工具与 Valve Corporation、赛事主办方、HLTV.org **无任何隶属关系**。比赛 Demo 文件、游戏素材和战队名称的权利归各自权利人所有。项目使用 Awpy（MIT）完成 Demo 解析与相关 artifact 工作流；雷达图所含游戏图像权利仍归其原权利人，不自动属于项目代码许可证。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

---

## 验证

```powershell
python -m py_compile app.py                          # 编译检查
python scripts/audit_v4_release.py                   # 发布审计（20/20）
python -m pytest -q tests/test_replay_state_machine.py  # 回放状态机（34 passed）
python -m pytest -q                                  # 全量（350 passed）
python -m pytest -q tests/test_showcase_bundle.py    # Showcase 专项（32 passed）
```
