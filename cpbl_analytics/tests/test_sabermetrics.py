from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest

from cpbl_analytics.sabermetrics import (
    add_batting_advanced_metrics,
    add_pitching_advanced_metrics,
    pythagorean_win_pct,
    team_batting_aggregates,
)
from cpbl_analytics.scraper.batting import fetch_batting_stats
from cpbl_analytics.scraper.pitching import fetch_pitching_stats

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _batting_df() -> pd.DataFrame:
    stats = fetch_batting_stats(html=_read("batting_sample.html"))
    return pd.DataFrame([asdict(s) for s in stats])


def _pitching_df() -> pd.DataFrame:
    stats = fetch_pitching_stats(html=_read("pitching_sample.html"))
    return pd.DataFrame([asdict(s) for s in stats])


def test_iso_equals_slg_minus_avg():
    df = add_batting_advanced_metrics(_batting_df())
    row = df[df["player_name"] == "王大明"].iloc[0]
    assert abs(row["iso"] - (row["slg"] - row["avg"])) < 1e-9


def test_team_batting_aggregates_groups_by_team():
    df = add_batting_advanced_metrics(_batting_df())
    team_df = team_batting_aggregates(df)
    assert set(team_df["team_name"]) == {"中信兄弟", "統一7-ELEVEn獅"}
    cx = team_df[team_df["team_name"] == "中信兄弟"].iloc[0]
    assert cx["at_bats"] == 400 + 500


def test_pitching_advanced_metrics_ip_float():
    df = add_pitching_advanced_metrics(_pitching_df())
    row = df[df["player_name"] == "張投手"].iloc[0]
    assert row["ip_float"] == pytest.approx(150 + 2 / 3, abs=1e-3)


def test_pythagorean_win_pct_symmetric_when_equal_runs():
    assert pythagorean_win_pct(500, 500) == 0.5


def test_pythagorean_win_pct_higher_when_scoring_more():
    assert pythagorean_win_pct(600, 500) > 0.5
