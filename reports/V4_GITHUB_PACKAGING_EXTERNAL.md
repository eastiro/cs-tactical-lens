# V4 GitHub 发布包装与仓库整理报告

> 生成时间：2026-07-18

---

## 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `README.md` | **重写** | 从 V1/V2 单场叙事升级为 V4 完整产品主页 |
| `.gitignore` | **完善** | 从 7 条规则扩展到全面覆盖 |
| `data/README.md` | **新增** | 数据目录结构与数据边界说明 |
| `docs/GITHUB_RELEASE_CHECKLIST.md` | **新增** | 11 项发布前检查清单 |
| `reports/V4_GITHUB_PACKAGING_EXTERNAL.md` | **新增** | 本报告 |

**未修改**：`app.py`、`src/`、`tests/`、`scripts/`、数据文件。

---

## README 产品口径

关键变化：

| 旧版（V1/V2 口径） | 新版（V4 口径） |
|---|---|
| "验收案例：Team Falcons 13:8 FURIA，Mirage" | 删除，替换为可复用的 V4 能力描述 |
| "V1 已收口，正在推进 V2" | 删除 |
| "经济分类尚未解析 / unclassified" 作为全局现状 | 替换为"基于冻结结束快照的经济分级" |
| "当前导入器还没有经过验证的冻结结束经济快照" | 替换为当前状态描述 |
| "多场同图默认样本（下一阶段）" | 删除，V4 已完成此功能 |
| 产品工作流交代不详 | "Demo → bundle → profile → 比较 → 回放" 完整流水线 |
| 项目结构未反映 V4 模块 | 更新为 V4 完整模块列表 |
| 无数据规模 | 135 bundles、117 profiles、318 tests、20/20 audit |
| 无数据边界说明 | 明确 raw/processed 不提交，series/map_assets 可提交 |
| "测试覆盖…" 不准确 | 精确引用测试数与审计结果 |

---

## `.gitignore` 新增规则

| 类别 | 规则 |
|------|------|
| Python 产物 | `*.pyc`、`*.pyo`、`*.egg-info/`、`dist/`、`build/` |
| 覆盖率 | `.coverage`、`coverage/`、`htmlcov/`、`*.cover` |
| 虚拟环境 | `.venv/`、`venv/`、`env/` |
| 演示数据 | `*.dem`、`*.rar` |
| 流程文件 | `data/raw/`、`data/processed/` |
| 日志 | `logs/`、`*.log`、`data/*.log` |
| IDE/系统 | `.vscode/`、`.idea/`、`*.swp`、`*.swo`、`*~`、`.DS_Store`、`Thumbs.db` |
| 内部协作 | `tasks/external-agent/`、`docs/handoff/` |
| 根目录报告 | `reports/`（保留已发布的 3 份 QA 报告） |
| 地图 zip | `data/map_assets/maps.zip` |

---

## 公开 vs 本地数据

| 目录 | Git 状态 | 说明 |
|------|----------|------|
| `app.py`、`src/`、`scripts/`、`tests/` | **公开** | 核心源码与测试 |
| `data/series/` | **公开** | 轻量 team-map profile（每文件数十 KB） |
| `data/map_assets/*.png` | **公开**（需确认许可） | 运行播放器必需 |
| `data/catalog/` | **公开** | 地图索引 |
| `data/registry/` | **公开** | 比赛注册表 |
| `data/processed/` | **仅本地** | ~19 GB 规范化解构数据 |
| `data/raw/` | **仅本地** | ~48 GB 原始 Demo 包 |
| `tasks/external-agent/` | **仅本地** | 内部协作 |
| `docs/handoff/` | **仅本地** | 会话交接 |

---

## 仍需用户决定的事项

1. **许可证** — 未选择。建议候选：MIT / Apache-2.0
2. **仓库名** — 建议保持 `cs-demo-analyzer` 或使用 `cs-tactical-lens`
3. **截图** — 3–5 张脱敏截图或 GIF，放入 `docs/images/`
4. **雷达 PNG 再分发** — 确认 Valve 素材的再分发许可；如不确定，可从仓库排除
5. **Release tag** — 建议 `v4.0.0`
6. **GitHub topics** — 建议已在清单中列出

---

## 运行命令与结果

```powershell
# 编译检查
python -m py_compile app.py
# → 无错误

# 发布审计
python scripts/audit_v4_release.py
# → 20 passed, 0 failed, exit code 0
```

---

## 数据安全确认

- [x] **未删除**任何数据文件
- [x] **未移动**任何数据文件
- [x] **未重命名**任何数据文件
- [x] **未修改** `data/raw/`、`data/processed/`、`data/series/`
- [x] **未执行** `git init`、`git add`、`git commit`、`git push`
- [x] **未创建** GitHub 仓库
- [x] **未添加** LICENSE 文件（留给用户决定）
- [x] **未运行** Demo 导入或 profile 构建

## Codex 验收修正

- 修正 README 固定写成 0:20 的问题：V4 实际按经济类型使用 12/15/20 秒观察点。
- 修正“历史模型判定”表述：经济分类是冻结结束快照上的可解释确定性规则，不是训练模型。
- 修正 `.gitignore` 的 `reports/` 反向包含规则，并补充 `.env`、zip/7z、本地批处理入口。
- 隐私扫描发现 `data/catalog/` 与 `data/registry/` 含本机 `D:\...` 绝对路径，现已默认排除；`data/series/` 未发现本机绝对路径，继续作为轻量聚合结果保留。
- 修正纯代码克隆复现口径：编译和空语料启动可验证，完整 318 项测试与 20/20 审计需要维护者本地未公开 corpus。
- 使用独立临时 Git 目录模拟首次提交：742 个候选文件，总计 4.95 MB，最大文件 0.31 MB；未发现 raw、processed、catalog、registry、Demo、压缩包、日志或内部任务漏入。
- 使用同一候选清单构造无本地语料的干净目录：`python -m py_compile app.py` 通过，Streamlit `AppTest` 启动异常数为 0；缺失 bundle 时页面给出明确警告，不伪造回放入口。
