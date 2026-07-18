"""
回合局势时间线原型
===================
独立可运行的 Streamlit 页面，展示一回合内 T/CT 存活人数变化、
击杀节点、下包、拆包和爆炸事件。

视觉遵循 CS Tactical Lens 黑色战术室主题。

┌─────────────────────────────────────────────────────────┐
│  5 ┤ T ●═══●═══●═══●═══════════●═══●═══●═══●═══●      │
│  4 ┤    ║       ║   ║           ║   ║   ║   ║   ║      │
│  3 ┤    ╚═══●═══╝   ║           ║   ╚═══╝   ╚═══╝      │
│  2 ┤        ║       ╚═══●═══●═══╝                      │
│  1 ┤        ║           ║   ╚═══●═══●═══●═══●═══●      │
│  0 ┤●═══●═══╝           ╚═══●═══╝       ╚═══●═══●      │
│    └──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──   │
│      0  10  20  30  40  50  60  70  80  90  100  110    │
│      ← 炸弹爆炸                                          │
└─────────────────────────────────────────────────────────┘

用法：
  python -m streamlit run archive/prototypes/timeline_prototype.py

独立原型，不修改 src/ 和 app.py 现有逻辑。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import plotly.graph_objects as go
import streamlit as st

# ── 色彩常量（与 app.py 一致） ─────────────────────────────
T_COLOR = "#F0AA3C"
CT_COLOR = "#4DA3FF"
KILL_COLOR = "#FF5F65"
BOMB_COLOR = "#FF6B35"
DEFUSE_COLOR = "#47C97E"
EXPLOSION_COLOR = "#FF4444"

BG = "#080b0f"
SURFACE = "#0e131b"
BORDER = "#1c2330"
TEXT = "#e1e7ef"
MUTED = "#78869a"
DIM = "#4b5769"

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', 'Cascadia Code', ui-monospace, Consolas, monospace"


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class TimelineEvent:
    """时间线上的一个事件节点。"""

    seconds: float
    kind: Literal["kill", "bomb_plant", "bomb_defuse", "bomb_explosion"]
    attacker: str = ""
    victim: str = ""
    weapon: str = ""
    team: str = ""  # "T" 或 "CT"，阵营色决定标记颜色
    site: str = ""  # 下包/拆包位置
    note: str = ""

    @property
    def label(self) -> str:
        if self.kind == "kill":
            icon = "☠"
            return f"{self.attacker} → {self.victim} [{self.weapon}]"
        elif self.kind == "bomb_plant":
            icon = "◎"
            return f"C4 已安装 @ {self.site}区"
        elif self.kind == "bomb_defuse":
            icon = "🔧"
            return f"拆包中 — {self.attacker}"
        elif self.kind == "bomb_explosion":
            icon = "💥"
            return f"C4 爆炸！"
        return ""


# ── 模拟数据 ─────────────────────────────────────────────


def mock_round_events() -> list[TimelineEvent]:
    """生成一回合模拟局势数据（Round 8, Falcons vs FURIA, Mirage）。

    局势走向：
      T 方进攻 A 区 → 下包 → CT 回防 → 1v1 残局 → C4 爆炸，T 胜。
    """
    return [
        # seconds, kind, attacker, victim, weapon, team, site
        TimelineEvent(0.0, "kill", note="回合开始 · 5v5"),
        TimelineEvent(15.2, "kill", "FALCON|N", "FURIA|kye", "AK-47", "T"),
        TimelineEvent(22.8, "kill", "FURIA|qck", "FALCON|makk", "M4A4", "CT"),
        TimelineEvent(31.5, "kill", "FALCON|sany", "FURIA|fod", "Galil", "T"),
        TimelineEvent(38.0, "kill", "FALCON|N", "FURIA|arT", "AK-47", "T"),
        TimelineEvent(42.0, "bomb_plant", "FALCON|N", site="A"),
        TimelineEvent(50.5, "kill", "FURIA|gang", "FALCON|N", "M4A1-S", "CT"),
        TimelineEvent(60.0, "kill", "FURIA|qck", "FALCON|sany", "AWP", "CT"),
        TimelineEvent(68.0, "kill", "FALCON|ntx", "FURIA|qck", "AK-47", "T"),
        TimelineEvent(75.0, "kill", "FURIA|gang", "FALCON|zx", "M4A4", "CT"),
        TimelineEvent(82.0, "bomb_explosion", note="C4 爆炸 · T 方获胜 (2:1 存活)"),
    ]


def mock_round_events_ct_defuse() -> list[TimelineEvent]:
    """另一回合模拟数据：CT 拆包获胜。"""
    return [
        TimelineEvent(0.0, "kill", note="回合开始 · 5v5"),
        TimelineEvent(10.8, "kill", "FURIA|qck", "FALCON|makk", "AWP", "CT"),
        TimelineEvent(18.2, "kill", "FALCON|N", "FURIA|kye", "AK-47", "T"),
        TimelineEvent(26.5, "kill", "FALCON|ntx", "FURIA|fod", "Deagle", "T"),
        TimelineEvent(33.0, "kill", "FURIA|gang", "FALCON|sany", "M4A1-S", "CT"),
        TimelineEvent(40.0, "bomb_plant", "FALCON|N", site="B"),
        TimelineEvent(48.5, "kill", "FALCON|zx", "FURIA|arT", "AK-47", "T"),
        TimelineEvent(55.0, "kill", "FURIA|qck", "FALCON|ntx", "AWP", "CT"),
        TimelineEvent(62.0, "kill", "FALCON|N", "FURIA|gang", "AK-47", "T"),
        TimelineEvent(70.0, "kill", "FALCON|zx", "FURIA|qck", "AK-47", "T"),
        TimelineEvent(78.0, "bomb_defuse", "FURIA|kye", site="B"),
    ]


# ── 存活人数计算 ──────────────────────────────────────────


def survivor_curves(
    events: list[TimelineEvent],
) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    """从事件列表计算出 T/CT 存活人数随时间变化的阶梯序列。

    返回 (t_curve, ct_curve)，每个元素为 (seconds, alive_count)。
    """
    t_alive = 5
    ct_alive = 5

    t_curve: list[tuple[float, int]] = [(0.0, 5)]
    ct_curve: list[tuple[float, int]] = [(0.0, 5)]

    for ev in events:
        if ev.seconds == 0.0:
            continue
        if ev.kind == "kill":
            if ev.team == "T":
                ct_alive -= 1
            elif ev.team == "CT":
                t_alive -= 1
        # 爆炸或拆包不改变存活人数
        t_curve.append((ev.seconds, t_alive))
        ct_curve.append((ev.seconds, ct_alive))

    return t_curve, ct_curve


# ── 绘制函数 ──────────────────────────────────────────────


def render_timeline(
    events: list[TimelineEvent],
    selected_second: float | None = None,
    *,
    height: int = 240,
) -> go.Figure:
    """用 Plotly 绘制回合时间线。

    参数
    ----
    events : 时间线事件列表
    selected_second : 当前选中的回放时间（画竖线）
    height : 图表像素高度
    """
    t_curve, ct_curve = survivor_curves(events)
    max_time = max(ev.seconds for ev in events) + 5 if events else 115

    fig = go.Figure()

    # ── T 存活阶梯线 ──
    t_x = [p[0] for p in t_curve]
    t_y = [p[1] for p in t_curve]
    fig.add_trace(
        go.Scatter(
            x=t_x,
            y=t_y,
            mode="lines+markers",
            name="T",
            line=dict(color=T_COLOR, width=3, shape="hv"),
            marker=dict(
                size=6,
                color=T_COLOR,
                symbol="circle",
                line=dict(width=1, color="#080b0f"),
            ),
            hovertemplate="<b>T 存活</b>: %{y} 人<br>时刻: %{x:.1f} 秒<extra></extra>",
            legendgroup="survivor",
        )
    )

    # ── CT 存活阶梯线 ──
    ct_x = [p[0] for p in ct_curve]
    ct_y = [p[1] for p in ct_curve]
    fig.add_trace(
        go.Scatter(
            x=ct_x,
            y=ct_y,
            mode="lines+markers",
            name="CT",
            line=dict(color=CT_COLOR, width=3, shape="hv"),
            marker=dict(
                size=6,
                color=CT_COLOR,
                symbol="circle",
                line=dict(width=1, color="#080b0f"),
            ),
            hovertemplate="<b>CT 存活</b>: %{y} 人<br>时刻: %{x:.1f} 秒<extra></extra>",
            legendgroup="survivor",
        )
    )

    # ── 填充区域（存活人数之间的视觉差） ──
    # 在两曲线之间填充半透明色
    fig.add_trace(
        go.Scatter(
            x=t_x + list(reversed(ct_x)),
            y=t_y + list(reversed(ct_y)),
            fill="toself",
            fillcolor="rgba(77,163,255,0.06)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ── 事件标记（击杀 / 下包 / 拆包 / 爆炸） ──
    kill_x, kill_y = [], []
    kill_hover, kill_colors, kill_sizes, kill_symbols = [], [], [], []
    bomb_x, bomb_y = [], []
    bomb_hover, bomb_colors, bomb_symbols, bomb_sizes = [], [], [], []

    # 获取每个时刻的存活人数用于 y 轴定位
    t_dict = dict(t_curve)
    ct_dict = dict(ct_curve)

    def survivors_at(t: float) -> tuple[int, int]:
        t_surv = max(v for tt, v in t_curve if tt <= t)
        ct_surv = max(v for tt, v in ct_curve if tt <= t)
        return t_surv, ct_surv

    for ev in events:
        t_surv, ct_surv = survivors_at(ev.seconds)
        if ev.seconds == 0.0:
            continue

        if ev.kind == "kill":
            # 击杀事件标记放在被杀者阵营的存活人数位置
            victim_side = "CT" if ev.team == "T" else "T"
            y_pos = ct_surv if victim_side == "CT" else t_surv
            kill_x.append(ev.seconds)
            kill_y.append(y_pos)
            team_color = T_COLOR if ev.team == "T" else CT_COLOR
            kill_colors.append(team_color)
            kill_sizes.append(12)
            kill_symbols.append("diamond")
            killer_color = T_COLOR if ev.team == "T" else CT_COLOR
            kill_hover.append(
                f"<b>☠ 击杀</b><br>"
                f"<span style='color:{killer_color}'>{ev.attacker}</span> "
                f"→ {ev.victim}<br>"
                f"武器: {ev.weapon}<br>"
                f"时刻: {ev.seconds:.1f} 秒"
                f"<extra></extra>"
            )
        elif ev.kind == "bomb_plant":
            bomb_x.append(ev.seconds)
            bomb_y.append(max(t_surv, ct_surv) + 0.5)
            bomb_colors.append(BOMB_COLOR)
            bomb_symbols.append("star")
            bomb_sizes.append(14)
            bomb_hover.append(
                f"<b>◎ C4 已安装</b><br>"
                f"位置: {ev.site} 区<br>"
                f"安装者: {ev.attacker}<br>"
                f"时刻: {ev.seconds:.1f} 秒"
                f"<extra></extra>"
            )
        elif ev.kind == "bomb_defuse":
            bomb_x.append(ev.seconds)
            bomb_y.append(max(t_surv, ct_surv) + 0.5)
            bomb_colors.append(DEFUSE_COLOR)
            bomb_symbols.append("cross")
            bomb_sizes.append(14)
            bomb_hover.append(
                f"<b>🔧 拆包中</b><br>"
                f"拆包者: {ev.attacker}<br>"
                f"位置: {ev.site} 区<br>"
                f"时刻: {ev.seconds:.1f} 秒"
                f"<extra></extra>"
            )
        elif ev.kind == "bomb_explosion":
            bomb_x.append(ev.seconds)
            bomb_y.append(5.5)
            bomb_colors.append(EXPLOSION_COLOR)
            bomb_symbols.append("x")
            bomb_sizes.append(18)
            bomb_hover.append(
                f"<b>💥 C4 爆炸</b><br>"
                f"时刻: {ev.seconds:.1f} 秒"
                f"<extra></extra>"
            )

    if kill_x:
        fig.add_trace(
            go.Scatter(
                x=kill_x,
                y=kill_y,
                mode="markers",
                name="击杀",
                marker=dict(
                    size=kill_sizes,
                    color=kill_colors,
                    symbol=kill_symbols,
                    line=dict(width=1, color="#080b0f"),
                ),
                hovertemplate="%{hovertext}",
                hovertext=kill_hover,
                hoverlabel=dict(
                    bgcolor=SURFACE,
                    bordercolor=BORDER,
                    font=dict(color=TEXT, size=12, family=FONT),
                ),
                customdata=[[x] for x in kill_x],
                legendgroup="events",
            )
        )

    if bomb_x:
        fig.add_trace(
            go.Scatter(
                x=bomb_x,
                y=bomb_y,
                mode="markers",
                name="炸弹事件",
                marker=dict(
                    size=bomb_sizes,
                    color=bomb_colors,
                    symbol=bomb_symbols,
                    line=dict(width=2, color="#080b0f"),
                ),
                hovertemplate="%{hovertext}",
                hovertext=bomb_hover,
                hoverlabel=dict(
                    bgcolor=SURFACE,
                    bordercolor=BORDER,
                    font=dict(color=TEXT, size=12, family=FONT),
                ),
                customdata=[[x] for x in bomb_x],
                legendgroup="events",
            )
        )

    # ── 当前选中时间竖线 ──
    if selected_second is not None and 0 <= selected_second <= max_time:
        fig.add_vline(
            x=selected_second,
            line=dict(color="#eef3f8", width=2, dash="dot"),
            opacity=0.5,
            annotation_text=f"  {selected_second:.0f}s",
            annotation_position="top left",
            annotation_font=dict(color=MUTED, size=11, family=MONO),
        )

    # ── 布局 ──
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=24, b=36),
        paper_bgcolor=BG,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=TEXT),
        hovermode="closest",
        dragmode=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=MUTED),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=dict(text="回合时间 (秒)", font=dict(size=11, color=MUTED, family=MONO)),
            range=[-2, max_time],
            tickfont=dict(size=10, color=DIM, family=MONO),
            gridcolor="#1a212c",
            zeroline=False,
            dtick=10,
        ),
        yaxis=dict(
            title=dict(text="存活", font=dict(size=11, color=MUTED, family=MONO)),
            range=[-0.3, 6.3],
            tickfont=dict(size=10, color=DIM, family=MONO),
            gridcolor="#1a212c",
            zeroline=False,
            dtick=1,
            tickmode="array",
            tickvals=[0, 1, 2, 3, 4, 5],
            ticktext=["0", "1", "2", "3", "4", "5"],
        ),
    )

    return fig


# ── 积分卡 ────────────────────────────────────────────────


def render_stats_panel(events: list[TimelineEvent]) -> str:
    """生成回合统计 HTML 面板。"""
    kills_t = sum(1 for e in events if e.kind == "kill" and e.team == "T")
    kills_ct = sum(1 for e in events if e.kind == "kill" and e.team == "CT")
    has_plant = any(e.kind == "bomb_plant" for e in events)
    has_defuse = any(e.kind == "bomb_defuse" for e in events)
    has_explosion = any(e.kind == "bomb_explosion" for e in events)
    total_kills = kills_t + kills_ct
    round_end = max(e.seconds for e in events) if events else 0

    outcome = ""
    if has_explosion:
        outcome = "💥 C4 爆炸 · T 胜"
    elif has_defuse:
        outcome = "🔧 拆包成功 · CT 胜"
    else:
        last_kill = [e for e in events if e.kind == "kill"]
        if last_kill:
            winner_team = last_kill[-1].team
            outcome = f"{'☠ T' if winner_team == 'T' else '☠ CT'} 全歼获胜"

    site_info = ""
    for e in events:
        if e.kind == "bomb_plant":
            site_info = f"下包 {e.site} 区"
            break

    return f"""
    <div style="
        display:grid; grid-template-columns:repeat(4,1fr); gap:0.7rem;
        margin:0.5rem 0 1rem; font-family:{MONO}; font-size:0.78rem;
    ">
      <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:3px; padding:0.55rem 0.7rem; text-align:center;">
        <div style="color:{MUTED}; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase;">时长</div>
        <div style="color:{TEXT}; font-weight:700; font-size:1.05rem;">{round_end:.0f}s</div>
      </div>
      <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:3px; padding:0.55rem 0.7rem; text-align:center;">
        <div style="color:{MUTED}; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase;">击杀</div>
        <div style="display:flex; justify-content:center; gap:1rem; margin-top:0.15rem;">
          <span style="color:{T_COLOR}; font-weight:700;">{kills_t}</span>
          <span style="color:{MUTED};">:</span>
          <span style="color:{CT_COLOR}; font-weight:700;">{kills_ct}</span>
        </div>
      </div>
      <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:3px; padding:0.55rem 0.7rem; text-align:center;">
        <div style="color:{MUTED}; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase;">炸弹</div>
        <div style="color:{TEXT}; font-weight:600;">
          {site_info if site_info else '—'}
        </div>
      </div>
      <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:3px; padding:0.55rem 0.7rem; text-align:center;">
        <div style="color:{MUTED}; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase;">结果</div>
        <div style="color:{TEXT}; font-weight:700; font-size:0.85rem;">{outcome}</div>
      </div>
    </div>
    """


# ── Streamlit 页面 ────────────────────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="CS Tactical Lens — 回合时间线原型",
        page_icon="◎",
        layout="wide",
    )

    # ── 全局暗色 CSS ──
    st.markdown(
        f"""
    <style>
      .stApp {{
        background: {BG};
        color: {TEXT};
        font-family: {FONT};
      }}
      .block-container {{
        max-width: 1440px;
        padding: 1.5rem 2rem 3rem;
      }}
      h1, h2, h3, p, label {{ color: {TEXT} !important; }}
      h1 {{ font-weight: 800; font-size: 1.45rem; letter-spacing: -0.025em; }}
      h2 {{ font-size: 1.05rem; font-weight: 700; }}
      #MainMenu, .stAppDeployButton, footer {{ display: none; }}
      header[data-testid="stHeader"] {{ background: transparent !important; height: 0 !important; }}
      [data-testid="stToolbar"] {{ display: none !important; }}
      div[role="radiogroup"] {{
        gap: 0; background: #0b0f14; border: 1px solid {BORDER};
        border-radius: 4px; overflow: hidden; display: inline-flex;
      }}
      div[role="radiogroup"] label {{
        background: transparent !important; border: none !important;
        padding: 0.4rem 1.1rem; color: {MUTED}; font-size: 0.8rem;
      }}
      div[role="radiogroup"] label:not(:last-child) {{ border-right: 1px solid {BORDER} !important; }}
      div[role="radiogroup"] label:has(input:checked) {{ background: #19212b !important; color: #fff; }}
      .section-label {{
        color: {DIM}; font: 600 0.62rem {MONO}; letter-spacing: 0.2em;
        text-transform: uppercase; margin: 0 0 0.5rem;
      }}
      .stAlert {{ background: {SURFACE}; border-color: {BORDER}; color: {TEXT}; }}
    </style>
    """,
        unsafe_allow_html=True,
    )

    # ── 头部 ──
    st.markdown(
        f"""
    <div style="display:flex;align-items:center;gap:0.45rem;color:{DIM};font:600 0.58rem/1.2 {MONO};letter-spacing:0.24em;text-transform:uppercase;margin-bottom:0.15rem;">
      <span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:#47c97e;box-shadow:0 0 10px rgba(71,201,126,0.75);"></span>
      TIMELINE PROTOTYPE · STANDALONE
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.title("CS Tactical Lens — 回合时间线")

    st.markdown(
        f'<div class="section-label">ROUND TIMELINE · 存活人数走势与关键事件</div>',
        unsafe_allow_html=True,
    )

    # ── 示例选择 ──
    scenario = st.radio(
        "示例回合",
        ["T 方 C4 爆炸获胜", "CT 方拆包获胜"],
        horizontal=True,
        label_visibility="collapsed",
    )

    events = (
        mock_round_events()
        if scenario == "T 方 C4 爆炸获胜"
        else mock_round_events_ct_defuse()
    )

    # ── 主时间线 ──
    fig = render_timeline(events, None, height=260)
    chart = st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False, "staticPlot": False},
        key="timeline_main",
    )

    # ── 统计面板 ──
    st.markdown(render_stats_panel(events), unsafe_allow_html=True)

    # ── 事件明细表 ──
    st.markdown(
        f'<div class="section-label">EVENT LOG · 按时间排序</div>',
        unsafe_allow_html=True,
    )

    for ev in events:
        if ev.seconds == 0.0:
            continue

        if ev.kind == "kill":
            team_icon = f"<span style='color:{T_COLOR if ev.team=='T' else CT_COLOR};font-weight:700;'>{'T' if ev.team=='T' else 'CT'}</span>"
            icon = "☠"
            desc = f"{team_icon} <b>{ev.attacker}</b> → {ev.victim} · {ev.weapon}"
        elif ev.kind == "bomb_plant":
            icon = "◎"
            desc = f"C4 已安装 @ <b>{ev.site}区</b> — {ev.attacker}"
        elif ev.kind == "bomb_defuse":
            icon = "🔧"
            desc = f"拆包中 — <b>{ev.attacker}</b> @ {ev.site}区"
        elif ev.kind == "bomb_explosion":
            icon = "💥"
            desc = f"<b>C4 爆炸！</b> {' '.join(ev.note.split(' · ')[:2])}"
        else:
            icon = "•"
            desc = ev.note

        st.markdown(
            f"""
        <div style="display:grid;grid-template-columns:50px 28px 1fr;gap:0.3rem;
                    padding:0.35rem 0;border-bottom:1px solid #181f29;align-items:center;">
          <div style="font:0.68rem {MONO};color:{DIM};text-align:right;">{ev.seconds:.1f}s</div>
          <div style="font-size:1.1rem;text-align:center;">{icon}</div>
          <div style="font-size:0.82rem;color:#ccd3dc;">{desc}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── 交互提示 ──
    st.info(
        "🖱 鼠标悬停时间线上的数据点查看详情。💎 菱形 = 击杀（黄 T / 蓝 CT），"
        "★ = 下包，✕ = 爆炸，✛ = 拆包。",
        icon="ℹ️",
    )

    # ── 接入说明 ──
    with st.expander("📋 接入真实数据所需字段"):
        st.markdown(
            """
        ### 数据合约 (Data Contract)

        当接入真实回放数据时，`render_timeline()` 函数期望的事件结构如下：

        ```python
        @dataclass
        class TimelineEvent:
            seconds: float          # 距回合开始的秒数
            kind: str               # "kill" | "bomb_plant" | "bomb_defuse" | "bomb_explosion"
            attacker: str           # 击杀者 / 下包者 / 拆包者
            victim: str             # 被击杀者（仅 kill）
            weapon: str             # 武器名（仅 kill）
            team: str               # "T" | "CT"（击杀者的阵营，决定标记颜色）
            site: str               # "A" | "B"（下包/拆包位置）
            note: str               # 附加说明文字
        ```

        #### 从 Demo 解析到 TimelineEvent 的映射

        | 事件类型 | 数据源字段 | 说明 |
        |---|---|---|
        | kill | `kills` 表 | `seconds`, `attacker`, `victim`, `weapon`, `attacker_side` → `team` |
        | bomb_plant | `grenades` 表 or `bomb_events` | `seconds`, `thrower` → `attacker`, `area` → `site` |
        | bomb_defuse | `grenades` 表 or `bomb_events` | `seconds`, `thrower` → `attacker`, `area` → `site` |
        | bomb_explosion | `rounds` 表 or `bomb_events` | `seconds`（从 round 的 `bomb_exploded_second` 获取） |

        #### 存活人数计算

        `survivor_curves()` 函数通过遍历 kill 事件推算每时刻 T/CT 存活人数：

        - 起始 5v5
        - `team="T"` 的 kill 事件使 CT 存活 -1
        - `team="CT"` 的 kill 事件使 T 存活 -1
        - 炸弹事件不影响存活人数

        如果真实数据包含 `rounds.winning_side`、`kills.attacker_side` 等字段，
        则不需要额外计算，只需将数据填入 `TimelineEvent` 即可。
        """,
            unsafe_allow_html=True,
        )


main()
