"""測試 latest_export.export_predictions()：算好的勝率預測有沒有正確匯出成 JSON。

只測這個函式（不是整個 export_dataset_csv／export_last_updated 這些既有、
單純的檔案 I/O），因為這是新加的、串接 predictions.py 邏輯的部分，值得
單獨驗證輸出的 JSON 結構是對的。
"""
from __future__ import annotations

import json

import pytest

from cpbl_analytics import latest_export
from cpbl_analytics.scraper.batting import BattingStat
from cpbl_analytics.scraper.pitching import PitchingStat
from cpbl_analytics.scraper.schedule import GameResult
from cpbl_analytics.scraper.standings import TeamStanding


def _standing(team_name: str, win_pct: float, **overrides) -> TeamStanding:
    defaults = dict(
        team_name=team_name, games=13, wins=8, losses=5, ties=0, win_pct=win_pct,
        games_behind=None, last_10="6-0-4", streak="勝2",
        home_record="4-0-2", away_record="4-0-3",
    )
    defaults.update(overrides)
    return TeamStanding(**defaults)


def _batter(team_name: str, runs: int) -> BattingStat:
    return BattingStat(
        player_name="測試打者", team_name=team_name, games=13, at_bats=50, runs=runs,
        hits=15, doubles=3, triples=0, home_runs=2, rbi=10, stolen_bases=1,
        caught_stealing=0, sac_bunts=0, sac_flies=0, walks=5, intentional_walks=0,
        hit_by_pitch=0, strikeouts=8, double_plays=1, avg=0.300, obp=0.350, slg=0.450, ops=0.800,
    )


def _pitcher(team_name: str, runs_allowed: int) -> PitchingStat:
    return PitchingStat(
        player_name="測試投手", team_name=team_name, games=5, wins=2, losses=1, saves=0,
        holds=0, innings_pitched_outs=90, hits_allowed=20, home_runs_allowed=2, walks=8,
        intentional_walks=0, hit_by_pitch=1, strikeouts=25, wild_pitches=0, balks=0,
        runs_allowed=runs_allowed, earned_runs=runs_allowed - 1, era=3.00,
    )


@pytest.fixture()
def isolated_latest_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(latest_export, "LATEST_DIR", tmp_path)
    return tmp_path


def test_export_predictions_writes_power_ratings_and_predictions_json(isolated_latest_dir):
    standings = [_standing("強隊", 0.700), _standing("弱隊", 0.300, last_10="4-0-6", home_record="1-0-4", away_record="2-0-3")]
    batting = [_batter("強隊", runs=60), _batter("弱隊", runs=30)]
    pitching = [_pitcher("強隊", runs_allowed=30), _pitcher("弱隊", runs_allowed=60)]
    schedule = [
        GameResult(date="07/29", away_team="弱隊", home_team="強隊", away_score=None, home_score=None, status="", venue="測試球場"),
        GameResult(date="07/28", away_team="弱隊", home_team="強隊", away_score=1, home_score=5, status="已完賽", venue="測試球場"),
    ]

    result_path = latest_export.export_predictions(
        standings=standings, batting=batting, pitching=pitching, schedule=schedule
    )

    assert result_path == isolated_latest_dir / "predictions.json"
    predictions = json.loads(result_path.read_text(encoding="utf-8"))
    assert len(predictions) == 1  # 只有一場還沒比出比分的比賽
    assert predictions[0]["home_team"] == "強隊"
    assert predictions[0]["home_win_prob"] > predictions[0]["away_win_prob"]

    power_ratings = json.loads((isolated_latest_dir / "power_ratings.json").read_text(encoding="utf-8"))
    assert {r["team_name"] for r in power_ratings} == {"強隊", "弱隊"}
    strong = next(r for r in power_ratings if r["team_name"] == "強隊")
    weak = next(r for r in power_ratings if r["team_name"] == "弱隊")
    assert strong["power_rating"] > weak["power_rating"]


def test_export_predictions_handles_missing_datasets_gracefully(isolated_latest_dir):
    # cli.py 的設計是「某個資料集這一輪抓取失敗」也不該讓這裡整個爆掉。
    result_path = latest_export.export_predictions(standings=[], batting=[], pitching=[], schedule=[])

    predictions = json.loads(result_path.read_text(encoding="utf-8"))
    power_ratings = json.loads((isolated_latest_dir / "power_ratings.json").read_text(encoding="utf-8"))
    assert predictions == []
    assert power_ratings == []
