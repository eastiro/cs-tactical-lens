# GitHub Release 发布前检查清单

> 用于 CS Tactical Lens V4 公开仓库发布前逐项确认。

Codex 已于 2026-07-18 完成一次只读发布模拟：候选提交约 **755 个文件 / 7.80 MB**（含 2.78 MB Showcase），最大文件 0.31 MB；干净无语料目录可编译并通过 Streamlit 启动检查，Showcase 按钮可成功加载回放。MIT 代码许可证已经确定；正式截图、GitHub 仓库创建与 Release 仍可在首个版本发布后继续补充。

---

## 1. README 与 V4 状态核对

- [ ] README 无 "V1 已收口，正在推进 V2" 类旧表述
- [ ] README 无 "当前版本只有 Team Falcons 13:8 FURIA"
- [ ] README 无 "经济分类尚未解析 / unclassified" 作为全局现状
- [ ] README 准确描述 V4 产品定位（跨队/跨图比较工作台，非单场演示）
- [ ] "快速开始"区分了"代码可运行"和"需要自行准备 Demo"
- [x] 350 passed / 20/20 audit 数据已写入（数字与当前测试结果一致）
- [x] README 链接到 `docs/RESEARCH_NOTE.md`（英文研究说明）和 `docs/RESEARCH_NOTE_ZH.md`（中文）
- [x] README 链接到 `THIRD_PARTY_NOTICES.md`

## 2. 许可证

- [x] 决定许可证类型：MIT
- [x] 将 LICENSE 文件放入根目录
- [x] 在 README 中注明

> 项目源代码采用 MIT License；游戏衍生素材不属于该许可证。

## 3. 雷达素材与第三方声明

- [ ] 确认 `data/map_assets/*.png` 的再分发权利
- [x] `THIRD_PARTY_NOTICES.md` 已创建，说明素材权利归属 Valve，不自动属于代码许可证
- [ ] 如不确认，考虑只保留说明文件，不在仓库中分发 PNG

## 4. 截图与视觉素材

- [ ] 准备 3–5 张脱敏截图或短 GIF：
  - 研究工作台跨队比较页面
  - 回放页面对比 Mirage 和 Dust2 的地图渲染
  - OB 式装备 HUD 可见的回放画面
  - 战术模式 Mirage 中文区域聚合
- [ ] 确认截图不含未公开数据
- [ ] 将截图放入 `docs/images/` 或 GitHub 仓库封面
- [ ] 在 README 中添加截图引用

> 当前仓库未嵌入截图。发布清单中标记为待办，README 不引用不存在截图路径。

## 5. `.gitignore` 检查

- [ ] `git check-ignore` 确认以下路径被排除：

```powershell
git check-ignore -v data/raw/
git check-ignore -v data/processed/
git check-ignore -v "*.dem"
git check-ignore -v "*.rar"
git check-ignore -v data/catalog/
git check-ignore -v data/registry/
```

- [ ] 确认 `data/series/` **未**被忽略
- [ ] 确认 `data/map_assets/*.png` **未**被忽略（除非决定不分发）
- [ ] 确认 `data/catalog/`、`data/registry/`、`data/intake-seeds/` 被忽略，避免公开本机绝对路径
- [ ] 确认 `.streamlit/secrets.toml` 被忽略
- [ ] 确认 `__pycache__/`、`.pytest_cache/` 被忽略
- [ ] 确认 `tasks/external-agent/`、`docs/handoff/` 被忽略
- [ ] 确认 `.gitattributes` 存在且包含正确的 LF/CRLF/binary 规则

```powershell
# 快速查看哪些文件会进入首次提交
git add --dry-run .
```

## 6. 大文件检查

- [ ] 检查 `git add` 前是否有意外的大文件（>10 MB）

```powershell
# 找大于 10 MB 的文件
powershell -c "Get-ChildItem -Recurse -File | Where-Object { \$_.Length -gt 10MB } | Select-Object FullName, Length"
```

- [ ] 确认没有将 `data/processed/` 或 `data/raw/` 中的文件加入 Git

## 7. 干净环境验证

- [ ] 在 `git clone` 后的新目录（无本地语料）中运行：

```powershell
python -m pip install -r requirements.txt
python -m py_compile app.py
```

- [x] 确认缺失本地数据时提示清晰（参考 `data/README.md`）
- [x] 启动 `streamlit run app.py` 确认页面正常显示 Showcase 按钮和手动选择入口
- [x] 点击 Showcase 按钮 → 加载成功 → 回放正常显示（32 项测试验证）
- [x] 点击"更换比赛" → Showcase 按钮重新出现
- [ ] 不在纯代码克隆中强求 `audit_v4_release.py` 20/20；该审计需要维护者完整本地 corpus

## 8. 安全与密钥

- [ ] 检查无 `.streamlit/secrets.toml` 进入提交
- [ ] 检查无 `.env`、`*.key`、`*token*`、`*credential*` 进入提交
- [ ] 检查 URL 或配置中无嵌入式 API key 或下载链接 token

```powershell
# 快速扫描常见敏感模式（不提交的文件不会显示）
git grep -n "api_key\|api_secret\|password\|token" -- ':!*.md'
```

## 9. GitHub 仓库设置

- [ ] 仓库描述（建议）：
  > CS2 demo 分析台：跨队伍、跨地图的多场接触前结构比较工作台。支持雷达回放、经济分类、装备 HUD 与回合级证据复核。
- [ ] Topics（建议）：
  > `cs2` `counter-strike-2` `demo-analyzer` `tactical-analysis` `streamlit` `data-science` `esports`
- [ ] 创建 V4 正式 Release（附发布说明）
- [ ] 打 tag：`v4.0.0` 或 `v4.0`

## 10. 简历项目描述（建议）

```
CS Tactical Lens — 一个开源的 CS2 比赛 Demo 分析台，
把 135 场已验证 Demo 组织为 117 个 team-map research profile，
支持跨队伍/跨地图的接触前结构比较、经济分类和 OB 式装备 HUD 回放。
全部结论可回到具体比赛回合的雷达地图和道具时间线复核。
V4 已完成，通过 350 项测试和 20/20 发布审计。
```

## 11. 工程文件

- [x] `.gitattributes` 已创建：Python/MD/JSON/CSV 等文本文件使用 LF，Windows 脚本使用 CRLF，媒体文件标记为 binary
- [x] `THIRD_PARTY_NOTICES.md` 已创建：涵盖 Valve/CS2 素材、Awpy 许可、Demo 权利、项目许可证状态
- [x] `docs/RESEARCH_NOTE.md` / `docs/RESEARCH_NOTE_ZH.md` 已创建

## 12. V5 定位

- [ ] README 中 V5 描述为"生产化方向"，**不是** "V4 未修 Bug"
- [ ] V4 发布说明中不暗示 V4 尚未完成

---

## 首次提交前快速检查

```powershell
# 1. 检查哪些文件将被提交
git add --dry-run .

# 2. 检查 gitignore 是否生效
git check-ignore data/raw/ data/processed/

# 3. 大文件扫描
Get-ChildItem -Recurse -File | Where-Object { $_.Length -gt 10MB }

# 4. 检查 .gitattributes 存在
dir .gitattributes

# 5. 编译检查
python -m py_compile app.py

# 6. Showcase 测试
python -m pytest -q tests/test_showcase_bundle.py --tb=short

# 7. 审计
python scripts/audit_v4_release.py

# 8. 全量测试（耗时较长，发布前至少跑一次）
python -m pytest -q
```
