"""測試 validation.py 的交叉驗證邏輯：

1. 用「內部邏輯自洽」的樣本資料，驗證應該全部通過。
2. 故意在資料裡塞一筆矛盾的數字，驗證檢查真的抓得到。
"""
from __future__ import annotations

from pathlib import Path

from cpbl_analytics.scraper.batting import fetch_batting_stats
from cpbl_analytics.scraper.pitching import fetch_pitching_stats
from cpbl_analytics.scraper.standings import fetch_standings
from cpbl_analytics.validation import (
    validate_batting_stats,
    validate_pitching_stats,
    validate_standings,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_standings_validation_passes_on_consistent_sample():
    standings = fetch_standings(html=_read("standings_sample.html"))
    report = validate_standings(standings)
    assert report.all_passed, [c.message for c in report.checks if not c.passed]


def test_standings_validation_catches_win_pct_mismatch():
    standings = fetch_standings(html=_read("standings_sample.html"))
    standings[0].win_pct = 0.999  # 故意塞一個跟 62/(62+38) 對不上的勝率
    report = validate_standings(standings)
    assert not report.all_passed
    failing_names = [c.name for c in report.checks if not c.passed]
    assert "勝率 = 勝 / (勝+負) 交叉驗證" in failing_names


def test_batting_validation_passes_on_consistent_sample():
    stats = fetch_batting_stats(html=_read("batting_sample.html"))
    report = validate_batting_stats(stats)
    assert report.all_passed, [c.message for c in report.checks if not c.passed]


def test_batting_validation_catches_avg_mismatch():
    stats = fetch_batting_stats(html=_read("batting_sample.html"))
    stats[0].avg = 0.999  # 跟 H/AB 對不上
    report = validate_batting_stats(stats)
    assert not report.all_passed
    failing_names = [c.name for c in report.checks if not c.passed]
    assert "打擊率 AVG = 安打 / 打數 交叉驗證" in failing_names


def test_batting_validation_catches_impossible_hits_gt_at_bats():
    stats = fetch_batting_stats(html=_read("batting_sample.html"))
    stats[0].hits = stats[0].at_bats + 1
    report = validate_batting_stats(stats)
    assert not report.all_passed


def test_pitching_validation_passes_on_consistent_sample():
    stats = fetch_pitching_stats(html=_read("pitching_sample.html"))
    report = validate_pitching_stats(stats)
    assert report.all_passed, [c.message for c in report.checks if not c.passed]


def test_pitching_validation_catches_era_mismatch():
    stats = fetch_pitching_stats(html=_read("pitching_sample.html"))
    stats[0].era = 0.01  # 跟自責分/局數對不上
    report = validate_pitching_stats(stats)
    assert not report.all_passed
    failing_names = [c.name for c in report.checks if not c.passed]
    assert "防禦率 ERA 交叉驗證" in failing_names
