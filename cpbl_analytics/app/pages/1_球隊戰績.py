"""球隊戰績分頁：戰績表、勝率圖、畢氏勝率期望值（實際勝率 vs 理論勝率）。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_batting, get_pitching, get_standings, team_color
from cpbl_analytics.sabermetrics import (
    pythagorean_win_pct,
    team_batting_aggregates,
    team_pitching_aggregates,
)

st.set_page_config(page_title="球隊戰績 - CPBL 數據分析", page_icon="🏆", layout="wide")
st.title("🏆 球隊戰績")

standings = get_standings()
if standings.empty:
    empty_state("尚未有球隊戰績資料。")
    st.stop()

standings = standings.sort_values("win_pct", ascending=False).reset_index(drop=True)

st.subheader("戰績表")
display_cols = ["rank", "team_name", "games", "wins", "losses", "ties", "win_pct", "games_behind", "last_10", "streak"]
display_cols = [c for c in display_cols if c in standings.columns]
st.dataframe(
    standings[display_cols].rename(columns={
        "rank": "名次", "team_name": "球隊", "games": "出賽數", "wins": "勝", "losses": "負",
        "ties": "和", "win_pct": "勝率", "games_behind": "勝差", "last_10": "近十場", "streak": "連勝/敗",
    }),
    hide_index=True,
)

st.subheader("勝率排名")
fig = go.Figure()
fig.add_bar(
    x=standings["win_pct"],
    y=standings["team_name"],
    orientation="h",
    marker_color=[team_color(t) for t in standings["team_name"]],
    text=[f"{v:.3f}" for v in standings["win_pct"]],
    textposition="outside",
)
fig.update_layout(
    xaxis_title="勝率",
    yaxis=dict(autorange="reversed"),
    height=100 + 40 * len(standings),
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig)

st.divider()
st.subheader("畢氏勝率期望值（實際勝率 vs 理論勝率）")
st.caption(
    "理論勝率 = 由「總得分 / 總失分」用畢氏定理（Pythagenpat）推算出的期望勝率。"
    "實際勝率明顯高於理論值，代表這支球隊可能在關鍵分差比賽中特別會贏（牛棚穩、"
    "打線關鍵時刻表現好，或單純運氣好）；反之則可能有「大勝小輸」的傾向。"
)

batting = get_batting()
pitching = get_pitching()

if batting.empty or pitching.empty:
    st.info("需要同時有打者與投手數據才能計算畢氏勝率期望值（用團隊得分/失分推算）。")
else:
    team_bat = team_batting_aggregates(batting)[["team_name", "runs"]].rename(columns={"runs": "runs_scored"})
    team_pit = team_pitching_aggregates(pitching)[["team_name", "runs_allowed"]]
    merged = standings.merge(team_bat, on="team_name", how="left").merge(team_pit, on="team_name", how="left")
    merged = merged.dropna(subset=["runs_scored", "runs_allowed"])

    if merged.empty:
        st.info("球隊名稱在戰績表與球員數據表之間對不起來，暫時無法計算（可能是隊名寫法不一致）。")
    else:
        merged["expected_win_pct"] = merged.apply(
            lambda r: pythagorean_win_pct(r["runs_scored"], r["runs_allowed"]), axis=1
        )
        merged["luck_delta"] = (merged["win_pct"] - merged["expected_win_pct"]).round(3)

        fig2 = go.Figure()
        fig2.add_bar(name="實際勝率", x=merged["team_name"], y=merged["win_pct"], marker_color="#2a78d6")
        fig2.add_bar(name="理論勝率（畢氏）", x=merged["team_name"], y=merged["expected_win_pct"], marker_color="#898781")
        fig2.update_layout(barmode="group", yaxis_title="勝率", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2)

        st.dataframe(
            merged[["team_name", "runs_scored", "runs_allowed", "win_pct", "expected_win_pct", "luck_delta"]]
            .rename(columns={
                "team_name": "球隊", "runs_scored": "得分", "runs_allowed": "失分",
                "win_pct": "實際勝率", "expected_win_pct": "理論勝率", "luck_delta": "差距",
            })
            .sort_values("差距", ascending=False),
            hide_index=True,
        )
