"""資料驗證分頁：本平台如何確保抓到的數字是正確的。

這是整支程式最重要的一個分頁。這裡不是「相信爬蟲」，而是把每一次爬蟲
執行時做過的交叉驗證（用最基礎欄位重新計算 AVG/OBP/SLG/OPS/ERA/WHIP，
跟官網顯示的數字比對）全部攤開，讓你自己判斷這批資料能不能信任。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from cpbl_analytics.app.utils import get_latest_validation_summary, get_scrape_runs

st.set_page_config(page_title="資料驗證 - CPBL 數據分析", page_icon="🔍", layout="wide")
st.title("🔍 資料驗證")

st.markdown(
    """
### 這個平台怎麼確保「抓到的東西是對的」

每次執行 `python -m cpbl_analytics.cli scrape` 時，程式會：

1. **只用表頭文字比對欄位**，不是用第幾欄位置去猜——官網改版、欄位順序調換時，
   會直接丟出解析錯誤，而不是安靜地把資料塞到錯的欄位。
2. **用最基礎的數字重新驗算衍生指標**：打擊率(AVG) = 安打/打數、上壘率(OBP)、
   長打率(SLG)、OPS、防禦率(ERA)、WHIP，全部重新計算一次跟官網顯示的數字比對，
   對不上就標記為警告或錯誤。
3. **邏輯一致性檢查**：安打數不能超過打數、出賽數要等於勝+負+和、
   全聯盟總勝場要等於總敗場等等。
4. **把每次執行的結果存進資料庫**，包含通過/失敗的每一項檢查，全部呈現在這個頁面，
   而不是只告訴你「成功」兩個字。

如果下面完全沒有資料，代表你還沒執行過 `cli scrape`（見 README「快速開始」）。
"""
)

st.divider()

runs = get_scrape_runs(limit=50)

if not runs.empty:
    # 本機開發情境：sqlite 裡有完整的歷史執行紀錄，顯示完整歷史表格。
    st.subheader("執行歷史（本機 sqlite）")
    st.dataframe(
        runs[["dataset", "scraped_at", "year", "row_count", "error_count", "warning_count", "all_passed"]]
        .rename(columns={
            "dataset": "資料集", "scraped_at": "執行時間(UTC)", "year": "年度",
            "row_count": "筆數", "error_count": "錯誤數", "warning_count": "警告數",
            "all_passed": "全部通過",
        }),
        hide_index=True,
    )

    st.divider()
    st.subheader("最近一次各資料集的詳細驗證結果")

    for dataset in runs["dataset"].unique():
        latest = runs[runs["dataset"] == dataset].iloc[0]
        status = "✅ 全部通過" if latest["all_passed"] else f"❌ {latest['error_count']} 項錯誤、{latest['warning_count']} 項警告"
        with st.expander(f"{dataset}（{latest['scraped_at']}）— {status}", expanded=not bool(latest["all_passed"])):
            checks = json.loads(latest["report_json"])
            for check in checks:
                icon = "✅" if check["passed"] else ("🛑" if check["severity"] == "error" else "⚠️")
                st.write(f"{icon} **{check['name']}**：{check['message']}")
                for item in check.get("offending_items", [])[:10]:
                    st.write(f"　　- {item}")
else:
    # 雲端部署情境：沒有本機 sqlite 歷史，改讀 GitHub Actions 每次爬蟲後
    # commit 回 repo 的 data/latest/validation_summary.json（只有「最新一次」，
    # 沒有歷史，但一樣完整揭露每一項檢查的結果）。
    summary = get_latest_validation_summary()
    if summary is None:
        st.info("尚未有任何爬蟲執行紀錄。")
        st.stop()

    st.subheader(f"最近一次驗證結果（產生於 {summary['generated_at']}，UTC）")
    st.caption(
        "這份結果是 GitHub Actions 排程爬蟲之後 commit 回 repo 的快照，"
        "檔案本身也可以直接在 GitHub 上開啟：`data/latest/validation_summary.json`。"
    )

    for dataset, info in summary["datasets"].items():
        status = "✅ 全部通過" if info["all_passed"] else f"❌ {info['error_count']} 項錯誤、{info['warning_count']} 項警告"
        with st.expander(f"{dataset} — {status}", expanded=not info["all_passed"]):
            for check in info["checks"]:
                icon = "✅" if check["passed"] else ("🛑" if check["severity"] == "error" else "⚠️")
                st.write(f"{icon} **{check['name']}**：{check['message']}")
                for item in check.get("offending_items", [])[:10]:
                    st.write(f"　　- {item}")
