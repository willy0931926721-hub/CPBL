"""比賽勝率預測分頁：球隊實力評分 + 近期賽程勝率預測。

這裡只提供「我們自己用數據算出來的機率」，不會、也不打算串接任何博弈網站
的賠率（見 cpbl_analytics/predictions.py 開頭的完整說明：合法的台灣運彩
賠率頁面本身就需要會員登入、也有反爬蟲保護，貿然嘗試繞過在技術上不可靠、
條款上也很可能不被允許）。想比對賠率的話，這裡提供一個「你自己輸入賠率」
的小工具，計算隱含機率、跟我們預測的機率兩者的落差，但賠率數字要你自己
去合法管道查。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import streamlit as st

from cpbl_analytics.app.utils import empty_state, get_batting, get_pitching, get_schedule, get_standings, team_color
from cpbl_analytics.predictions import compute_team_power_ratings, predict_matchup, predict_upcoming_games

st.set_page_config(page_title="比賽勝率預測 - CPBL 數據分析", page_icon="🎯", layout="wide")
st.title("🎯 比賽勝率預測")

st.info(
    "本頁呈現的機率是根據歷史數據（球季戰績、畢氏勝率期望值、近況、主客場優勢）"
    "算出的統計估計值，**不是**內線消息、也不保證比賽結果，更不構成任何投注建議。"
    "本頁不會、也不會串接任何博弈網站的賠率——想比對賠率，賠率數字要你自己從合法"
    "管道查詢後手動輸入。若涉及任何形式的投注，請透過合法管道進行、並注意相關法規、"
    "量力而為。"
)

standings = get_standings()
batting = get_batting()
pitching = get_pitching()
schedule = get_schedule()

if standings.empty:
    empty_state("尚未有球隊戰績資料，無法計算球隊實力評分。")
    st.stop()

power_ratings = compute_team_power_ratings(standings, batting, pitching)

st.subheader("球隊實力評分")
st.caption(
    "power_rating = 畢氏勝率期望值（50%）+ 球季實際勝率（30%）+ 近十場戰績勝率（20%）"
    "的加權平均，任一項缺資料時會自動把權重分給其他項目。方法論細節見 "
    "`cpbl_analytics/predictions.py` 的模組說明。"
)
ranked = power_ratings.sort_values("power_rating", ascending=False).reset_index(drop=True)

fig = go.Figure()
fig.add_bar(
    x=ranked["power_rating"],
    y=ranked["team_name"],
    orientation="h",
    marker_color=[team_color(t) for t in ranked["team_name"]],
    text=[f"{v:.3f}" for v in ranked["power_rating"]],
    textposition="outside",
)
fig.update_layout(
    xaxis_title="實力評分",
    yaxis=dict(autorange="reversed"),
    height=100 + 40 * len(ranked),
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig)

st.dataframe(
    ranked[[
        "team_name", "power_rating", "pythagorean_win_pct", "season_win_pct",
        "recent_form_win_pct", "home_win_pct", "away_win_pct",
    ]].rename(columns={
        "team_name": "球隊", "power_rating": "實力評分", "pythagorean_win_pct": "畢氏期望勝率",
        "season_win_pct": "球季勝率", "recent_form_win_pct": "近十場勝率",
        "home_win_pct": "主場勝率", "away_win_pct": "客場勝率",
    }),
    hide_index=True,
)

st.divider()
st.subheader("近期賽程勝率預測")

if schedule.empty:
    st.info("尚未有賽程資料，無法列出即將開打的比賽。")
else:
    upcoming_predictions = predict_upcoming_games(schedule, power_ratings)
    if upcoming_predictions.empty:
        st.info(
            "目前賽程資料裡沒有找到「還沒比出比分」的比賽——可能是本季賽程都已比完、"
            "官網賽程頁目前查到的月份範圍不包含未來場次，或是兩隊裡有一隊還沒有戰績資料。"
        )
    else:
        for _, game in upcoming_predictions.iterrows():
            with st.container(border=True):
                st.markdown(
                    f"**{game['game_date']}**　{game['away_team']} @ {game['home_team']}"
                    + (f"　·　{game['venue']}" if game.get("venue") else "")
                )
                c1, c2 = st.columns(2)
                c1.metric(f"{game['away_team']}（客）勝率", f"{game['away_win_prob']:.1%}")
                c2.metric(f"{game['home_team']}（主）勝率", f"{game['home_win_prob']:.1%}")

                with st.expander("輸入你自己查到的賠率，比對隱含機率"):
                    st.caption(
                        "賠率格式：歐洲盤（例如 1.90 代表押 100 元贏 90 元、連本金拿回 190 元）。"
                        "隱含機率 = 1 / 賠率；「差距」= 我們預測的機率 − 隱含機率，正值代表"
                        "我們的模型比賠率隱含的機率更看好這隊贏、可能是有價值的機會，"
                        "但也可能是我們的模型漏掉了賠率反映出的資訊（例如當天先發投手），"
                        "純供參考，不是下注建議。"
                    )
                    oc1, oc2 = st.columns(2)
                    away_odds = oc1.number_input(
                        f"{game['away_team']}（客）賠率", min_value=1.01, value=1.90, step=0.01,
                        key=f"away_odds_{game['game_date']}_{game['away_team']}_{game['home_team']}",
                    )
                    home_odds = oc2.number_input(
                        f"{game['home_team']}（主）賠率", min_value=1.01, value=1.90, step=0.01,
                        key=f"home_odds_{game['game_date']}_{game['away_team']}_{game['home_team']}",
                    )
                    away_implied = 1 / away_odds
                    home_implied = 1 / home_odds
                    rc1, rc2 = st.columns(2)
                    rc1.metric(
                        f"{game['away_team']} 隱含機率 vs 預測機率",
                        f"{away_implied:.1%}",
                        f"{(game['away_win_prob'] - away_implied):+.1%}",
                    )
                    rc2.metric(
                        f"{game['home_team']} 隱含機率 vs 預測機率",
                        f"{home_implied:.1%}",
                        f"{(game['home_win_prob'] - home_implied):+.1%}",
                    )

st.divider()
st.subheader("自訂對戰試算")
st.caption("不受限於實際賽程，任選兩支球隊，看看模型算出來的對戰勝率。")

all_teams = sorted(power_ratings["team_name"].unique())
if len(all_teams) < 2:
    st.info("目前收錄的球隊不到兩支，無法試算。")
else:
    sc1, sc2 = st.columns(2)
    sim_home = sc1.selectbox("主隊", all_teams, index=0)
    sim_away = sc2.selectbox("客隊", all_teams, index=min(1, len(all_teams) - 1))

    if sim_home == sim_away:
        st.warning("請選擇兩支不同的球隊。")
    else:
        sim_result = predict_matchup(sim_home, sim_away, power_ratings)
        if sim_result is None:
            st.warning("其中一支球隊目前沒有足夠的戰績資料，無法預測。")
        else:
            rc1, rc2 = st.columns(2)
            rc1.metric(f"{sim_away}（客）勝率", f"{sim_result['away_win_prob']:.1%}")
            rc2.metric(f"{sim_home}（主）勝率", f"{sim_result['home_win_prob']:.1%}")

st.caption(
    "限制：目前的預測只反映「兩支球隊」的整體實力（球季戰績、近況、主客場優勢），"
    "**不包含當天先發投手的臨時優劣勢**——官網賽程頁目前還沒確認「未開賽」比賽會不會"
    "列出先發投手，等這部分資料源確認可用後會再把先發投手的防禦率/WHIP 等指標納入模型。"
)
