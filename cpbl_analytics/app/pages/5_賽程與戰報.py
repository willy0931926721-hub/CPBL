"""賽程與戰報分頁：近期賽果一覽。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_schedule

st.set_page_config(page_title="賽程與戰報 - CPBL 數據分析", page_icon="📅", layout="wide")
st.title("📅 賽程與戰報")

schedule = get_schedule()
if schedule.empty:
    empty_state("尚未有賽程資料。")
    st.stop()

with st.sidebar:
    st.header("篩選條件")
    status_options = sorted(schedule["status"].dropna().unique())
    selected_status = st.multiselect("比賽狀態", status_options, default=status_options)

filtered = schedule[schedule["status"].isin(selected_status)] if selected_status else schedule

st.dataframe(
    filtered[["game_date", "away_team", "away_score", "home_team", "home_score", "status", "venue"]]
    .rename(columns={
        "game_date": "日期", "away_team": "客隊", "away_score": "客隊得分",
        "home_team": "主隊", "home_score": "主隊得分", "status": "狀態", "venue": "球場",
    }),
    hide_index=True,
    height=700,
)

st.caption(
    "本頁只呈現爬蟲抓到的賽程卡片欄位；若欄位是空的，代表官網當下的版面跟 "
    "`cpbl_analytics/scraper/schedule.py` 裡設定的 CSS selector 對不上，"
    "請參考 README「已知限制」章節更新 selector。"
)
