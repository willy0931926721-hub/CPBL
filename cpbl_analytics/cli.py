"""命令列工具：實際對官網跑一次完整爬蟲 + 驗證 + 寫入資料庫 + 匯出快照。

使用方式：
    python -m cpbl_analytics.cli scrape --year 2026

注意：這支程式需要能連上 https://www.cpbl.com.tw 的網路環境才能運作。
若在沒有對外網路的沙盒/CI 環境執行，會直接拿到連線錯誤，這是預期行為，
不代表程式邏輯有問題（可參考 README「已知限制」章節）。

這支程式也是 `.github/workflows/scrape.yml` 排程用的進入點：GitHub Actions
會定期執行這支程式，把 data/latest/ 底下匯出的 CSV／JSON 快照 commit 回 repo，
讓部署在 Streamlit Community Cloud 上的網頁版不需要仰賴任何人手動開電腦
更新資料。
"""
from __future__ import annotations

import argparse
import sys

from cpbl_analytics import latest_export, storage
from cpbl_analytics.scraper.batting import fetch_batting_stats
from cpbl_analytics.scraper.http import FetchError, ParsingError
from cpbl_analytics.scraper.pitching import fetch_pitching_stats
from cpbl_analytics.scraper.schedule import fetch_schedule
from cpbl_analytics.scraper.standings import fetch_standings
from cpbl_analytics.validation import (
    ValidationReport,
    validate_batting_stats,
    validate_pitching_stats,
    validate_schedule,
    validate_standings,
)


def _print_report(dataset: str, report: ValidationReport) -> None:
    status = "✅ 全部通過" if report.all_passed else "❌ 有檢查未通過"
    print(f"\n[{dataset}] 驗證結果：{status}")
    for check in report.checks:
        mark = "✅" if check.passed else ("🛑" if check.severity == "error" else "⚠️")
        print(f"  {mark} {check.name}: {check.message}")
        for item in check.offending_items[:5]:
            print(f"       - {item}")


# 常見的分頁預設「每頁筆數」——如果抓到的筆數剛好是這幾個數字之一，很可能
# 代表分頁展開沒有生效（例如 _try_expand_page_size 找到的下拉選單跟真正
# 控制筆數的選單不是同一個），而不是這個球季剛好就只有這麼多人。這裡只是
# 印出來提醒，不會讓這次執行失敗——資料本身沒有錯，只是可能不完整。
_SUSPICIOUS_PAGE_SIZE_COUNTS = {10, 15, 20, 25, 30, 50}


def _warn_if_suspicious_row_count(dataset: str, row_count: int) -> None:
    if row_count in _SUSPICIOUS_PAGE_SIZE_COUNTS:
        print(
            f"⚠️ [{dataset}] 只抓到 {row_count} 筆，這剛好是常見的分頁預設筆數，"
            "可能還有更多資料被分頁隱藏（見 scraper/http.py 的 "
            "_try_expand_page_size 說明），不代表資料本身有錯，但值得留意。"
        )


def cmd_scrape(args: argparse.Namespace) -> int:
    storage.init_db()
    exit_code = 0
    reports: dict[str, ValidationReport] = {}
    # 這幾個變數保留「這次執行實際抓到的原始資料」，給最後匯出
    # predictions.json／power_ratings.json 用（見下面 export_predictions()）。
    # 初始化成空 list，這樣某個資料集這一輪剛好抓取失敗時，後面的預測匯出
    # 步驟頂多算出比較不完整的結果，而不會直接整個報錯中斷。
    standings: list = []
    batting: list = []
    pitching: list = []
    games: list = []

    try:
        print("正在抓取球隊戰績...")
        standings = fetch_standings()
        report = validate_standings(standings)
        reports["standings"] = report
        storage.save_standings(standings, year=args.year)
        storage.save_scrape_run(dataset="standings", report=report, row_count=len(standings), year=args.year)
        latest_export.export_dataset_csv("standings", standings)
        _print_report("球隊戰績", report)
        if not report.all_passed:
            exit_code = 1
    except (FetchError, ParsingError) as exc:
        print(f"🛑 球隊戰績抓取失敗：{exc}")
        exit_code = 1

    try:
        print("\n正在抓取打者數據...")
        batting = fetch_batting_stats(year=args.year)
        report = validate_batting_stats(batting)
        reports["batting"] = report
        storage.save_batting(batting, year=args.year)
        storage.save_scrape_run(dataset="batting", report=report, row_count=len(batting), year=args.year)
        latest_export.export_dataset_csv("batting", batting)
        _print_report("打者數據", report)
        _warn_if_suspicious_row_count("打者數據", len(batting))
        if not report.all_passed:
            exit_code = 1
    except (FetchError, ParsingError) as exc:
        print(f"🛑 打者數據抓取失敗：{exc}")
        exit_code = 1

    try:
        print("\n正在抓取投手數據...")
        pitching = fetch_pitching_stats(year=args.year)
        report = validate_pitching_stats(pitching)
        reports["pitching"] = report
        storage.save_pitching(pitching, year=args.year)
        storage.save_scrape_run(dataset="pitching", report=report, row_count=len(pitching), year=args.year)
        latest_export.export_dataset_csv("pitching", pitching)
        _print_report("投手數據", report)
        _warn_if_suspicious_row_count("投手數據", len(pitching))
        if not report.all_passed:
            exit_code = 1
    except (FetchError, ParsingError) as exc:
        print(f"🛑 投手數據抓取失敗：{exc}")
        exit_code = 1

    try:
        print("\n正在抓取賽程與戰報...")
        games = fetch_schedule()
        report = validate_schedule(games)
        reports["schedule"] = report
        storage.save_schedule(games)
        storage.save_scrape_run(dataset="schedule", report=report, row_count=len(games), year=args.year)
        latest_export.export_dataset_csv("schedule", games)
        _print_report("賽程與戰報", report)
        if not report.all_passed:
            exit_code = 1
    except (FetchError, ParsingError) as exc:
        print(f"🛑 賽程抓取失敗：{exc}")
        exit_code = 1

    if reports:
        latest_export.export_validation_summary(reports)
        latest_export.export_last_updated(year=args.year)
        print(f"\n已匯出最新快照到 {latest_export.LATEST_DIR}（會被 GitHub Actions commit 回 repo）")

    # 算球隊實力評分／近期賽程勝率預測，給 Next.js 網站（web/）用。這是
    # 額外的加值輸出，不是核心資料正確性的一部分，所以刻意包一層 try/except：
    # 就算這裡算出問題，也不該讓已經抓好、驗證通過的 standings/batting/
    # pitching/schedule 資料無法 commit 回 repo。
    try:
        latest_export.export_predictions(
            standings=standings, batting=batting, pitching=pitching, schedule=games
        )
        print("已匯出球隊實力評分／賽程勝率預測（power_ratings.json／predictions.json）")
    except Exception as exc:  # noqa: BLE001 - 這裡出錯不該擋住其他資料集的 commit
        print(f"⚠️ 匯出勝率預測時發生錯誤（不影響其他資料集）：{exc}")

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpbl_analytics", description="CPBL 數據爬蟲與驗證 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape_parser = sub.add_parser("scrape", help="抓取球隊戰績、打者、投手數據並寫入資料庫")
    scrape_parser.add_argument("--year", type=int, default=None, help="指定球季年度（預設為官網當前顯示的球季）")
    scrape_parser.set_defaults(func=cmd_scrape)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
