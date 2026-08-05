"""投手排行榜分頁：完整投球數據 + 進階指標，可依球隊/最低局數篩選。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_pitching, team_color
from cpbl_analytics.sabermetrics import add_pitching_advanced_metrics

st.set_page_config(page_title="投手排行榜 - CPBL 數據分析", page_icon="⚾", layout="wide")
st.title("⚾ 投手排行榜")

pitching = get_pitching()
if pitching.empty:
    empty_state("尚未有投手數據。")
    st.stop()

pitching = add_pitching_advanced_metrics(pitching)

with st.sidebar:
    st.header("篩選條件")
    teams = sorted(pitching["team_name"].unique())
    selected_teams = st.multiselect("球隊", teams, default=teams)
    max_ip = float(pitching["ip_float"].max()) if not pitching["ip_float"].isna().all() else 0.0
    min_ip = st.slider("最低投球局數（篩掉樣本過少的投手）", 0.0, max_ip, min(20.0, max_ip))

filtered = pitching[pitching["team_name"].isin(selected_teams) & (pitching["ip_float"] >= min_ip)]

if filtered.empty:
    st.warning("目前篩選條件下沒有符合的投手，請放寬篩選條件。")
    st.stop()

st.caption(f"共 {len(filtered)} 位投手符合篩選條件（全部 {len(pitching)} 位）")

tab1, tab2 = st.tabs(["基本投球數據", "進階指標"])

with tab1:
    basic_cols = [
        "player_name", "team_name", "games", "games_started", "wins", "losses", "saves",
        "holds", "innings_pitched_outs", "strikeouts", "walks", "era", "whip",
    ]
    display = filtered[basic_cols].copy()
    display["局數"] = (display["innings_pitched_outs"] // 3).astype(str) + "." + (display["innings_pitched_outs"] % 3).astype(str)
    display = display.drop(columns=["innings_pitched_outs"])
    st.dataframe(
        display.rename(columns={
            "player_name": "球員", "team_name": "球隊", "games": "出賽", "games_started": "先發",
            "wins": "勝", "losses": "敗", "saves": "救援成功", "holds": "中繼",
            "strikeouts": "三振", "walks": "四壞", "era": "防禦率", "whip": "WHIP",
        })
        .sort_values("防禦率"),
        hide_index=True,
        height=600,
    )

with tab2:
    st.caption(
        "FIP 近似值採用常見預設常數（3.10），嚴謹分析應改用該球季聯盟平均自責分率反推球季專屬常數；"
        "此處數值適合用於同球季球員間的相對比較。"
    )
    adv_cols = ["player_name", "team_name", "ip_float", "k_per_9", "bb_per_9", "hr_per_9", "k_bb_ratio", "fip_approx"]
    st.dataframe(
        filtered[adv_cols]
        .rename(columns={
            "player_name": "球員", "team_name": "球隊", "ip_float": "局數(十進位)",
            "k_per_9": "K/9", "bb_per_9": "BB/9", "hr_per_9": "HR/9",
            "k_bb_ratio": "K/BB", "fip_approx": "FIP(近似)",
        })
        .sort_values("FIP(近似)"),
        hide_index=True,
        height=600,
    )

st.divider()
st.subheader("Top 10")
metric_label = st.selectbox("排行指標", ["era", "strikeouts", "saves", "whip", "fip_approx"], format_func=lambda x: {
    "era": "防禦率", "strikeouts": "奪三振", "saves": "救援成功", "whip": "WHIP", "fip_approx": "FIP(近似)",
}[x])
ascending = metric_label in ("era", "whip", "fip_approx")  # 這些指標越低越好

top10 = filtered.sort_values(metric_label, ascending=ascending).head(10)
fig = go.Figure()
fig.add_bar(
    x=top10[metric_label],
    y=top10["player_name"],
    orientation="h",
    marker_color=[team_color(t) for t in top10["team_name"]],
)
fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10), height=450)
if ascending:
    fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig)
