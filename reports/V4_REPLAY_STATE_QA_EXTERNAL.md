# V4 回放状态机与跨地图 UI 验收报告

> 生成时间：2026-07-18
> 底验 Task 36：20/20 ✅

## 测试总览

| 文件 | 测试数 | 结果 |
|------|--------|------|
| `tests/test_replay_state_machine.py` | **34** | ✅ 全部通过 |
| `tests/test_v3_view.py` | **13** | ✅（已有，未修改） |
| `tests/test_tactical_view.py` | **2** | ✅（已有，未修改） |
| `tests/test_loadout_timeline.py` | **4** | ✅（已有，未修改） |
| `scripts/audit_v4_release.py` | 20 checks | ✅ 全部通过 |
| **合计** | **73 tests + 20 audits** | **全部通过** |

## 覆盖的状态路径

```
R1:  空回放页 → 无默认比赛 → profile selector 存在 → 无 scoreboard
R2:  → 选择 profile → 选择 match → 加载 → selected_round 出现 → map name 正确
R3:  → 已加载 → 点击"更换比赛" → bundle 清空 → selectors 重现 → 无异常
R4:  → manual bundle 存在 → load evidence → manual 被清理（反向亦然）
R5:  → 非 Mirage bundle → 标题不含 "Mirage" → 含真实地图名
R6:  → include_loadout=True 传入 round_playback_html → payload 含 loadoutTimeline
R7:  → Mirage 战术模式正常渲染 → 非 Mirage 显示边界提示并安全停止
R8:  → Team Spirit == Spirit / Team Falcons == Falcons → 去重正确
```

## 修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/test_replay_state_machine.py` | **新增** | 34 项测试覆盖 R1-R8 |
| `reports/V4_REPLAY_STATE_QA_EXTERNAL.md` | **新增** | 本报告 |

**未修改** `app.py`、已有测试、数据文件。

## 发现的问题

本次验收 **未发现需要修复的产品 Bug**。所有需求（R1-R8）在现有代码中表现正确。

### 细节说明

- **R6 验证**：`app.py:2549` 的唯一 `round_playback_html` 调用传入 `include_loadout=True`。两种回放路径（手动/证据）走同一调用路径，自动继承该参数。
- **R4 互斥**：`jump_to_series_replay()` 明确 `pop("manual_replay_bundle")`；手动加载按钮 `pop("active_replay_bundle")`。两方向互斥在函数级和 AppTest 双重验证。
- **R5 非 Mirage 标题**：地图名全部使用 `data.map_name.replace('de_', '').upper()` 动态生成，无固定字符串。
- **R7 边界**：非 Mirage 战术模式在 `data.map_name != "de_mirage"` 时 `st.info()` + `st.stop()`，不抛异常，其他页面正常可用。

## 未自动覆盖的页面风险

1. **HTML iframe 内像素**：AppTest 不支持读取 iframe 内容；HUD 渲染正确性需手动验证。
2. **多场样本页面**：未安排独立测试，但通过 replay/report 路径间接覆盖（共用 `data_loaded` 与 `load_match`）。
3. **Streamlit `st.rerun()` 时序**：AppTest 中 rerun 后的页面可能无法完整模拟；通过两次 `at.run()` 补偿。

## 精确命令

```powershell
# 编译检查
python -m py_compile app.py

# 运行全部相关测试
python -m pytest -q tests/test_replay_state_machine.py tests/test_v3_view.py tests/test_tactical_view.py tests/test_loadout_timeline.py --tb=short

# 底层审计（Task 36）
python scripts/audit_v4_release.py
```

## 验收标准自查

- [x] R1-R8 均有明确实现或测试证据
- [x] 新测试不把比赛数量、队名展示前缀或文件排序写死（使用动态发现）
- [x] 不破坏 Task 36 的 20/20 底层审计
- [x] 没有触碰原始 Demo 与处理后 corpus
- [x] 报告可被 Codex 独立复跑和定位

## Codex 最终验收

- 源码检查：新增测试没有空断言，也没有用 mock 绕过回放核心路径。
- 全量复跑：`318 passed in 302.33s`。
- 发布审计复跑：`20 passed, 0 failed / 20 checks`。
- 浏览器人工验收：空回放、Dust2 手动加载、横向 HUD 与“更换比赛”清理路径通过。
- 说明：上表“测试数”按测试定义统计；pytest 对参数化用例展开后，任务指定文件实际输出为 80 passed。两种数字口径不同，不代表缺少用例。
