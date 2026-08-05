"""打者排行榜分頁：完整打擊數據 + 進階指標，可依球隊/最低打數篩選。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_batting, team_color
from cpbl_analytics.sabermetrics import add_batting_advanced_metrics

st.set_page_config(page_title="打者排行榜 - CPBL 數據分析", page_icon="🏏", layout="wide")
st.title("🏏 打者排行榜")

batting = get_batting()
if batting.empty:
    empty_state("尚未有打者數據。")
    st.stop()

batting = add_batting_advanced_metrics(batting)

with st.sidebar:
    st.header("篩選條件")
    teams = sorted(batting["team_name"].unique())
    selected_teams = st.multiselect("球隊", teams, default=teams)
    min_ab = st.slider("最低打數（篩掉打席過少的球員）", 0, int(batting["at_bats"].max()), 50)

filtered = batting[batting["team_name"].isin(selected_teams) & (batting["at_bats"] >= min_ab)]

if filtered.empty:
    st.warning("目前篩選條件下沒有符合的球員，請放寬篩選條件。")
    st.stop()

st.caption(f"共 {len(filtered)} 位球員符合篩選條件（全部 {len(batting)} 位）")

tab1, tab2 = st.tabs(["基本打擊數據", "進階指標"])

with tab1:
    basic_cols = [
        "player_name", "team_name", "games", "at_bats", "runs", "hits", "doubles",
        "triples", "home_runs", "rbi", "stolen_bases", "walks", "strikeouts",
        "avg", "obp", "slg", "ops",
    ]
    basic_cols = [c for c in basic_cols if c in filtered.columns]
    st.dataframe(
        filtered[basic_cols]
        .rename(columns={
            "player_name": "球員", "team_name": "球隊", "games": "出賽", "at_bats": "打數",
            "runs": "得分", "hits": "安打", "doubles": "二安", "triples": "三安",
            "home_runs": "全壘打", "rbi": "打點", "stolen_bases": "盜壘", "walks": "四壞",
            "strikeouts": "三振", "avg": "打擊率", "obp": "上壘率", "slg": "長打率", "ops": "OPS",
        })
        .sort_values("OPS", ascending=False),
        hide_index=True,
        height=600,
    )

with tab2:
    st.caption(
        "wOBA 近似值採用文獻上通用的簡化權重，未針對 CPBL 逐年得分環境校正，"
        "適合用來做球員間的相對排序，不建議直接跟其他聯盟的 wOBA 數值比較絕對大小。"
    )
    adv_cols = [
        "player_name", "team_name", "pa_est", "iso", "bb_rate", "k_rate", "babip", "woba_approx",
    ]
    st.dataframe(
        filtered[adv_cols]
        .rename(columns={
            "player_name": "球員", "team_name": "球隊", "pa_est": "打席(估)", "iso": "ISO",
            "bb_rate": "BB%", "k_rate": "K%", "babip": "BABIP", "woba_approx": "wOBA(近似)",
        })
        .sort_values("wOBA(近似)", ascending=False),
        hide_index=True,
        height=600,
    )

st.divider()
st.subheader("Top 10")
metric_label = st.selectbox("排行指標", ["avg", "home_runs", "rbi", "ops", "woba_approx"], format_func=lambda x: {
    "avg": "打擊率", "home_runs": "全壘打", "rbi": "打點", "ops": "OPS", "woba_approx": "wOBA(近似)",
}[x])

top10 = filtered.sort_values(metric_label, ascending=False).head(10)
fig = go.Figure()
fig.add_bar(
    x=top10[metric_label],
    y=top10["player_name"],
    orientation="h",
    marker_color=[team_color(t) for t in top10["team_name"]],
    text=[f"{v:.3f}" if isinstance(v, float) else str(v) for v in top10[metric_label]],
    textposition="outside",
)
fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10), height=450)
st.plotly_chart(fig)
