"""球隊比較分頁：任選 2 支以上球隊，用雷達圖比較打擊與投手綜合能力。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_batting, get_pitching, team_color
from cpbl_analytics.sabermetrics import team_batting_aggregates, team_pitching_aggregates

st.set_page_config(page_title="球隊比較 - CPBL 數據分析", page_icon="📊", layout="wide")
st.title("📊 球隊比較")

batting = get_batting()
pitching = get_pitching()

if batting.empty or pitching.empty:
    empty_state("需要同時有打者與投手數據才能做球隊比較。")
    st.stop()

team_bat = team_batting_aggregates(batting)
team_pit = team_pitching_aggregates(pitching)
all_teams = sorted(set(team_bat["team_name"]) | set(team_pit["team_name"]))

selected = st.multiselect("選擇要比較的球隊（至少 2 支）", all_teams, default=all_teams[: min(3, len(all_teams))])

if len(selected) < 2:
    st.info("請至少選擇 2 支球隊。")
    st.stop()

bat_sel = team_bat[team_bat["team_name"].isin(selected)].set_index("team_name")
pit_sel = team_pit[team_pit["team_name"].isin(selected)].set_index("team_name")


def normalize(series, *, higher_is_better: bool = True):
    lo, hi = series.min(), series.max()
    if hi == lo:
        return series * 0 + 0.5
    scaled = (series - lo) / (hi - lo)
    return scaled if higher_is_better else 1 - scaled


radar_metrics = {
    "打擊率": normalize(bat_sel["avg"]),
    "上壘率": normalize(bat_sel["obp"]),
    "長打率": normalize(bat_sel["slg"]),
    "全壘打": normalize(bat_sel["home_runs"]),
    "防禦率(佳)": normalize(pit_sel["era"], higher_is_better=False),
    "WHIP(佳)": normalize(pit_sel["whip"], higher_is_better=False),
    "奪三振率": normalize(pit_sel["k_per_9"]),
}

fig = go.Figure()
categories = list(radar_metrics.keys())
for team in selected:
    values = [radar_metrics[m].get(team, 0.5) for m in categories]
    values.append(values[0])
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories + [categories[0]],
        fill="toself",
        name=team,
        line_color=team_color(team),
    ))
fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    showlegend=True,
    margin=dict(l=40, r=40, t=40, b=40),
)
st.plotly_chart(fig)
st.caption(
    "雷達圖上的數值是把每一項指標依「目前選取的球隊」重新正規化到 0~1（1 代表選取範圍內最好），"
    "只適合比較彼此的相對強弱，不代表跟聯盟其他球隊比較的絕對名次。"
    "防禦率、WHIP 已經反轉方向（數值越靠外圈代表投手表現越好）。"
)

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("打擊數據")
    st.dataframe(
        bat_sel.reset_index()[["team_name", "at_bats", "runs", "hits", "home_runs", "rbi", "avg", "obp", "slg", "ops"]]
        .rename(columns={
            "team_name": "球隊", "at_bats": "打數", "runs": "得分", "hits": "安打",
            "home_runs": "全壘打", "rbi": "打點", "avg": "打擊率", "obp": "上壘率",
            "slg": "長打率", "ops": "OPS",
        }),
        hide_index=True,
    )
with col2:
    st.subheader("投手數據")
    st.dataframe(
        pit_sel.reset_index()[["team_name", "wins", "losses", "saves", "ip_float", "strikeouts", "era", "whip"]]
        .rename(columns={
            "team_name": "球隊", "wins": "勝", "losses": "敗", "saves": "救援成功",
            "ip_float": "局數", "strikeouts": "三振", "era": "防禦率", "whip": "WHIP",
        }),
        hide_index=True,
    )
