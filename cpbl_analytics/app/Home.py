"""CPBL 數據分析 - 網頁版首頁。

啟動方式（在專案根目錄下）：
    streamlit run cpbl_analytics/app/Home.py

這支程式用 Streamlit 內建的多頁面（multipage app）功能：本檔案是入口頁，
`pages/` 目錄底下的每一個檔案會自動變成左側導覽列的一個分頁。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 讓 `streamlit run cpbl_analytics/app/Home.py` 在任何工作目錄下都能
# import 到 cpbl_analytics 這個套件。
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_batting, get_last_updated, get_pitching, get_standings

st.set_page_config(
    page_title="CPBL 數據分析",
    page_icon="⚾",
    layout="wide",
)

st.title("⚾ 中華職棒（CPBL）數據分析平台")
st.caption("以官方網站數據為基礎的球隊 / 球員數據分析工具，供個人研究與分析使用。")

standings = get_standings()
batting = get_batting()
pitching = get_pitching()
last_updated = get_last_updated()

if standings.empty and batting.empty and pitching.empty:
    empty_state("目前沒有任何資料。")
else:
    last_scrape = last_updated["scraped_at"] if last_updated else "未知"
    st.caption(f"最近一次資料更新時間（UTC）：{last_scrape}　·　資料來源會由 GitHub Actions 排程自動更新")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("目前收錄球隊數", len(standings) if not standings.empty else 0)
    with col2:
        st.metric("收錄打者人數", len(batting) if not batting.empty else 0)
    with col3:
        st.metric("收錄投手人數", len(pitching) if not pitching.empty else 0)
    with col4:
        if not standings.empty:
            leader = standings.sort_values("win_pct", ascending=False).iloc[0]
            st.metric("目前戰績龍頭", leader["team_name"], f"勝率 {leader['win_pct']:.3f}")

    st.divider()

    if not batting.empty:
        st.subheader("打擊三圍領先者")
        top_avg = batting.sort_values("avg", ascending=False).iloc[0]
        top_hr = batting.sort_values("home_runs", ascending=False).iloc[0]
        top_ops = batting.sort_values("ops", ascending=False).iloc[0] if batting["ops"].notna().any() else None
        c1, c2, c3 = st.columns(3)
        c1.metric("打擊率王", top_avg["player_name"], f"{top_avg['avg']:.3f}")
        c2.metric("全壘打王", top_hr["player_name"], f"{int(top_hr['home_runs'])} 支")
        if top_ops is not None:
            c3.metric("OPS 王", top_ops["player_name"], f"{top_ops['ops']:.3f}")

    if not pitching.empty:
        st.subheader("投手三圍領先者")
        qualified = pitching[pitching["innings_pitched_outs"] > 0]
        top_era = qualified.sort_values("era").iloc[0] if not qualified.empty else None
        top_so = pitching.sort_values("strikeouts", ascending=False).iloc[0]
        top_sv = pitching.sort_values("saves", ascending=False).iloc[0]
        c1, c2, c3 = st.columns(3)
        if top_era is not None:
            c1.metric("防禦率王", top_era["player_name"], f"{top_era['era']:.2f}")
        c2.metric("奪三振王", top_so["player_name"], f"{int(top_so['strikeouts'])} K")
        c3.metric("救援成功王", top_sv["player_name"], f"{int(top_sv['saves'])} 次")

st.divider()
st.markdown(
    """
### 左側導覽

- **球隊戰績**：戰績表、勝率圖、畢氏勝率期望值比較
- **打者排行榜**：可篩選球隊/排序的完整打擊數據 + 進階指標（wOBA 近似值、ISO、BB%、K%）
- **投手排行榜**：完整投球數據 + 進階指標（FIP 近似值、K/9、BB/9）
- **球隊比較**：任選兩支以上球隊，多維度比較
- **賽程與戰報**：近期賽果
- **比賽勝率預測**：球隊實力評分（畢氏期望值/近況/主客場優勢）、即將開打
  比賽的勝率預測，可自行輸入查到的賠率比對隱含機率（不提供、也不串接
  任何博弈網站的賠率）
- **資料驗證**：本平台如何確保抓到的數字是正確的，所有交叉驗證結果都攤在這裡

### 關於資料正確性

本平台**不直接相信**官網頁面上顯示的打擊率、防禦率等衍生數字，而是用最基礎的欄位
（安打數、打數、局數、自責分...）重新計算一次，並與官網顯示的數字比對。
只要兩者對不上，就會在「資料驗證」頁面顯示為警告或錯誤，方便你自行判斷資料是否可信，
而不是盲目相信爬蟲抓到的每一個數字。
"""
)
