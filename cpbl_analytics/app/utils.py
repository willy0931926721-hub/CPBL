"""Streamlit 網頁版共用工具：資料載入（含快取）、配色、共用元件。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from cpbl_analytics import latest_export, storage
from cpbl_analytics.config import TEAM_NAMES
from cpbl_analytics.validation import ValidationReport

# 分類色票（8 色，固定順序，來自 dataviz 色彩驗證流程；每支球隊固定對應
# 同一個色號，不會因為篩選條件不同而重新分配顏色）。
CATEGORICAL_PALETTE = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

STATUS_COLORS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

TEAM_COLOR_MAP = {
    team: CATEGORICAL_PALETTE[i % len(CATEGORICAL_PALETTE)]
    for i, team in enumerate(TEAM_NAMES)
}


def team_color(team_name: str) -> str:
    return TEAM_COLOR_MAP.get(team_name, "#898781")  # 未知球隊用中性灰


def _year_filter(df: pd.DataFrame, year: int | None) -> pd.DataFrame:
    if year is not None and "year" in df.columns:
        return df[df["year"] == year]
    return df


# 每個資料載入函式都「優先讀 data/latest/*.csv」（GitHub Actions 排程爬蟲後
# commit 回 repo 的最新快照，Streamlit Cloud 部署版一定讀得到這份），
# 只有在本機開發、還沒有這份 CSV 時，才退回去讀本機的 sqlite（存有完整
# 歷史快照，但不會進版控、部署到雲端後不保證還在）。


@st.cache_data(ttl=300, show_spinner="讀取球隊戰績資料...")
def get_standings(year: int | None = None) -> pd.DataFrame:
    df = latest_export.load_dataset_csv("standings")
    if df is not None:
        return _year_filter(df, year)
    return storage.load_latest_standings(year=year)


@st.cache_data(ttl=300, show_spinner="讀取打者數據...")
def get_batting(year: int | None = None) -> pd.DataFrame:
    df = latest_export.load_dataset_csv("batting")
    if df is not None:
        return _year_filter(df, year)
    return storage.load_latest_batting(year=year)


@st.cache_data(ttl=300, show_spinner="讀取投手數據...")
def get_pitching(year: int | None = None) -> pd.DataFrame:
    df = latest_export.load_dataset_csv("pitching")
    if df is not None:
        return _year_filter(df, year)
    return storage.load_latest_pitching(year=year)


@st.cache_data(ttl=300, show_spinner="讀取賽程資料...")
def get_schedule() -> pd.DataFrame:
    df = latest_export.load_dataset_csv("schedule")
    if df is not None:
        return df
    return storage.load_latest_schedule()


@st.cache_data(ttl=60, show_spinner=False)
def get_scrape_runs(limit: int = 30) -> pd.DataFrame:
    return storage.load_scrape_runs(limit=limit)


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_validation_summary() -> dict | None:
    return latest_export.load_validation_summary()


@st.cache_data(ttl=60, show_spinner=False)
def get_last_updated() -> dict | None:
    return latest_export.load_last_updated()


def render_validation_report(report: ValidationReport, *, title: str) -> None:
    """在頁面上用一致的樣式呈現一份驗證報告。"""
    st.subheader(title)
    if report.all_passed:
        st.success(f"✅ 全部 {len(report.checks)} 項檢查通過")
    else:
        st.error(f"❌ {report.error_count} 項嚴重問題、{report.warning_count} 項警告")

    for check in report.checks:
        icon = "✅" if check.passed else ("🛑" if check.severity == "error" else "⚠️")
        with st.expander(f"{icon} {check.name}", expanded=not check.passed):
            st.write(check.message)
            if check.offending_items:
                st.write("問題項目（最多顯示 20 筆）：")
                for item in check.offending_items[:20]:
                    st.write(f"- {item}")


def empty_state(message: str) -> None:
    st.info(
        f"{message}\n\n"
        "尚未有資料。可能原因：\n"
        "1. 這是本機開發環境，還沒跑過 `python -m cpbl_analytics.cli scrape`；或\n"
        "2. 這是雲端部署版，但 GitHub Actions 排程爬蟲還沒有成功執行過一次\n"
        "   （去 repo 的 Actions 分頁確認 `定期更新 CPBL 資料` 這個 workflow 有沒有跑過／有沒有失敗）。\n\n"
        "詳見 README「自動化更新」章節。"
    )
