"""把「最新一次爬蟲結果」匯出成 CSV / JSON，存在 data/latest/ 底下並進版控。

為什麼需要這一層，而不是直接讓網頁版讀 storage.py 的 SQLite：

    SQLite 資料庫（data/cpbl.db）故意「不」進版控——它會隨著每次爬蟲執行
    不斷累積歷史快照，檔案只會越變越大，直接 commit 進 git 會讓 repo 無限
    膨脹。但這也代表：如果網頁版部署在 Streamlit Community Cloud 這種「從
    GitHub repo 直接建置、重啟後本機檔案系統會重置」的環境，SQLite 裡的資料
    在重新部署後就會消失。

    解法：GitHub Actions 排程爬蟲後，只把「最新一份快照」匯出成體積小、
    對 git diff 友善的 CSV／JSON，commit 回 repo。網頁版優先讀這裡的檔案，
    這樣即使 Streamlit Cloud 整個重新部署，資料還是從 git repo 裡帶著走，
    不需要本機一直開著、也不需要额外的資料庫服務。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from cpbl_analytics.config import LATEST_DIR
from cpbl_analytics.validation import ValidationReport

_FILENAMES = {
    "standings": "standings.csv",
    "batting": "batting.csv",
    "pitching": "pitching.csv",
    "schedule": "schedule.csv",
}


def export_dataset_csv(dataset: str, records: list[Any]) -> Path:
    """把一批爬蟲結果（dataclass 物件的 list）匯出成 CSV，覆蓋掉舊檔。"""
    path = LATEST_DIR / _FILENAMES[dataset]
    df = pd.DataFrame([asdict(r) for r in records])
    if dataset == "schedule" and "date" in df.columns:
        # GameResult.date 對應到 sqlite 那邊的 game_date 欄位名稱，
        # 統一成 game_date，這樣不管網頁版是讀 CSV 還是讀 sqlite，
        # 欄位名稱都一致，頁面程式不用寫兩套判斷。
        df = df.rename(columns={"date": "game_date"})
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def load_dataset_csv(dataset: str) -> pd.DataFrame | None:
    path = LATEST_DIR / _FILENAMES[dataset]
    if not path.exists():
        return None
    return pd.read_csv(path)


def export_validation_summary(reports: dict[str, ValidationReport]) -> Path:
    """把這次執行所有資料集的驗證結果，匯出成一份人類可讀的 JSON。

    刻意直接放在 repo 裡（不是只塞進資料庫），這樣不用跑任何程式，
    直接在 GitHub 網頁上點開這個檔案就能看到「最近一次抓的資料到底
    有沒有通過驗證」。
    """
    path = LATEST_DIR / "validation_summary.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {
            name: {
                "all_passed": report.all_passed,
                "error_count": report.error_count,
                "warning_count": report.warning_count,
                "checks": [
                    {
                        "name": c.name,
                        "passed": c.passed,
                        "severity": c.severity,
                        "message": c.message,
                        "offending_items": c.offending_items[:50],
                    }
                    for c in report.checks
                ],
            }
            for name, report in reports.items()
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_validation_summary() -> dict | None:
    path = LATEST_DIR / "validation_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def export_predictions(
    *,
    standings: list[Any],
    batting: list[Any],
    pitching: list[Any],
    schedule: list[Any],
) -> Path:
    """算出球隊實力評分與近期賽程勝率預測，匯出成 JSON 給 Next.js 網站用。

    刻意在這裡算好、直接輸出成 JSON，而不是讓前端（TypeScript）自己重新
    實作一次 log5 公式／貝氏小樣本收斂——這樣預測邏輯永遠只有 Python 這
    一份（cpbl_analytics/predictions.py），前端只負責呈現，不會出現「兩邊
    算出來的數字對不上」的風險。

    任何一個資料集是空的（例如那一輪爬蟲剛好失敗）都不會讓這裡整個炸掉，
    頂多算出比較不完整的結果（例如沒有打者/投手數據時，power_rating 只能
    用球季勝率），這樣才符合 cli.py 既有的「部分資料集失敗不擋住其他部分」
    設計。
    """
    from cpbl_analytics.predictions import compute_team_power_ratings, predict_upcoming_games

    standings_df = pd.DataFrame([asdict(r) for r in standings]) if standings else pd.DataFrame()
    batting_df = pd.DataFrame([asdict(r) for r in batting]) if batting else pd.DataFrame()
    pitching_df = pd.DataFrame([asdict(r) for r in pitching]) if pitching else pd.DataFrame()
    schedule_df = pd.DataFrame([asdict(r) for r in schedule]) if schedule else pd.DataFrame()
    if not schedule_df.empty and "date" in schedule_df.columns:
        # 跟 export_dataset_csv 的 schedule 分支一樣，統一欄位名稱。
        schedule_df = schedule_df.rename(columns={"date": "game_date"})

    power_ratings = compute_team_power_ratings(standings_df, batting_df, pitching_df)
    upcoming = (
        predict_upcoming_games(schedule_df, power_ratings)
        if not schedule_df.empty and not power_ratings.empty
        else pd.DataFrame()
    )

    power_ratings_path = LATEST_DIR / "power_ratings.json"
    power_ratings_path.write_text(
        power_ratings.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8"
    )

    predictions_path = LATEST_DIR / "predictions.json"
    predictions_path.write_text(
        upcoming.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8"
    )

    return predictions_path


def export_last_updated(*, year: int | None = None) -> Path:
    path = LATEST_DIR / "last_updated.json"
    path.write_text(
        json.dumps(
            {"scraped_at": datetime.now(timezone.utc).isoformat(), "year": year},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def load_last_updated() -> dict | None:
    path = LATEST_DIR / "last_updated.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
