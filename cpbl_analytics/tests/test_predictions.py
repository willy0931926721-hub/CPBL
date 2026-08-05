"""測試 predictions.py 的勝率預測邏輯（用人工設計的 DataFrame，不連外部網站）。"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from cpbl_analytics.predictions import (
    _shrink_toward,
    _wtl_stats,
    _wtl_win_pct,
    compute_team_power_ratings,
    log5_win_probability,
    predict_matchup,
    predict_upcoming_games,
)


def test_wtl_win_pct_parses_win_tie_loss_string():
    assert _wtl_win_pct("8-0-5") == pytest.approx(8 / 13)


def test_wtl_win_pct_returns_none_for_malformed_or_missing_values():
    assert _wtl_win_pct(None) is None
    assert _wtl_win_pct("") is None
    assert _wtl_win_pct("not-a-record") is None
    assert _wtl_win_pct("1-2") is None


def test_wtl_win_pct_returns_none_when_no_decisions_yet():
    assert _wtl_win_pct("0-0-0") is None


def test_wtl_stats_returns_win_pct_and_decision_count():
    assert _wtl_stats("8-0-5") == (pytest.approx(8 / 13), 13)
    assert _wtl_stats(None) == (None, 0)


def test_shrink_toward_returns_prior_when_no_sample():
    assert _shrink_toward(None, sample_size=0, prior_strength=10) == 0.5
    assert _shrink_toward(0.9, sample_size=0, prior_strength=10) == 0.5


def test_shrink_toward_pulls_small_samples_toward_prior():
    # 這是實際踩到的地雷：主場戰績「0 勝 0 和 3 敗」字面上是 0% 勝率，但只有
    # 3 場比賽，不該直接當成「這支球隊主場必輸」的真實實力來用。
    shrunk = _shrink_toward(0.0, sample_size=3, prior_strength=10)
    assert 0.0 < shrunk < 0.5
    assert shrunk == pytest.approx((3 * 0.0 + 10 * 0.5) / 13)


def test_shrink_toward_trusts_large_samples_almost_fully():
    shrunk = _shrink_toward(0.9, sample_size=1000, prior_strength=10)
    assert shrunk == pytest.approx(0.9, abs=0.01)


def _sample_standings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "team_name": "強隊",
                "games": 100,
                "win_pct": 0.700,
                "last_10": "8-0-2",
                "home_record": "20-0-5",
                "away_record": "15-0-10",
            },
            {
                "team_name": "弱隊",
                "games": 100,
                "win_pct": 0.300,
                "last_10": "2-0-8",
                "home_record": "10-0-15",
                "away_record": "5-0-20",
            },
        ]
    )


def _sample_batting() -> pd.DataFrame:
    # team_batting_aggregates 只需要 sum_cols 裡列出的欄位，這裡給最小可用集合。
    cols = [
        "team_name", "at_bats", "runs", "hits", "doubles", "triples", "home_runs",
        "rbi", "stolen_bases", "caught_stealing", "walks", "hit_by_pitch", "strikeouts",
    ]
    rows = [
        {"team_name": "強隊", "at_bats": 1000, "runs": 600, "hits": 300, "doubles": 50,
         "triples": 5, "home_runs": 40, "rbi": 280, "stolen_bases": 30, "caught_stealing": 10,
         "walks": 100, "hit_by_pitch": 10, "strikeouts": 200},
        {"team_name": "弱隊", "at_bats": 1000, "runs": 350, "hits": 250, "doubles": 30,
         "triples": 3, "home_runs": 15, "rbi": 150, "stolen_bases": 20, "caught_stealing": 15,
         "walks": 80, "hit_by_pitch": 8, "strikeouts": 250},
    ]
    return pd.DataFrame(rows, columns=cols)


def _sample_pitching() -> pd.DataFrame:
    cols = [
        "team_name", "wins", "losses", "saves", "holds", "innings_pitched_outs",
        "hits_allowed", "home_runs_allowed", "walks", "strikeouts", "runs_allowed", "earned_runs",
    ]
    rows = [
        {"team_name": "強隊", "wins": 70, "losses": 30, "saves": 25, "holds": 20,
         "innings_pitched_outs": 2700, "hits_allowed": 800, "home_runs_allowed": 60,
         "walks": 250, "strikeouts": 700, "runs_allowed": 400, "earned_runs": 370},
        {"team_name": "弱隊", "wins": 30, "losses": 70, "saves": 10, "holds": 15,
         "innings_pitched_outs": 2700, "hits_allowed": 1000, "home_runs_allowed": 100,
         "walks": 350, "strikeouts": 500, "runs_allowed": 650, "earned_runs": 600},
    ]
    return pd.DataFrame(rows, columns=cols)


def test_compute_team_power_ratings_ranks_strong_team_above_weak_team():
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    assert set(ratings["team_name"]) == {"強隊", "弱隊"}

    strong = ratings.set_index("team_name").loc["強隊"]
    weak = ratings.set_index("team_name").loc["弱隊"]

    assert strong["power_rating"] > weak["power_rating"]
    # 強隊得分遠高於失分，畢氏期望值應該明顯高於 0.5。
    assert strong["pythagorean_win_pct"] > 0.5
    assert weak["pythagorean_win_pct"] < 0.5
    assert strong["home_edge_vs_league"] > weak["home_edge_vs_league"]


def test_log5_win_probability_is_half_when_teams_are_equal():
    assert log5_win_probability(0.55, 0.55) == pytest.approx(0.5, abs=1e-9)


def test_log5_win_probability_favors_the_stronger_team():
    prob = log5_win_probability(0.7, 0.3)
    assert prob > 0.5


def test_predict_matchup_returns_none_for_unknown_team():
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    assert predict_matchup("強隊", "沒聽過的球隊", ratings) is None


def test_predict_matchup_gives_higher_win_prob_to_stronger_home_team():
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    result = predict_matchup("強隊", "弱隊", ratings)

    assert result is not None
    assert result["home_win_prob"] > result["away_win_prob"]
    assert math.isclose(result["home_win_prob"] + result["away_win_prob"], 1.0, abs_tol=1e-2)


def test_predict_matchup_avoids_extreme_probabilities_early_in_the_season():
    # 這是實際對真實資料跑出來的地雷：球季初期只打了 13~14 場，兩支實力其實
    # 差不多的球隊，光是因為某一隊客場戰績剛好是「0 勝 0 和 3 敗」這種小樣本，
    # log5 就會算出 99%/1% 這種不合理的極端預測。收斂之後不該再出現這麼極端
    # 的機率。
    standings = pd.DataFrame(
        [
            {
                "team_name": "A隊", "games": 13, "win_pct": 0.615,
                "last_10": "6-0-4", "home_record": "4-0-2", "away_record": "4-0-3",
            },
            {
                "team_name": "B隊", "games": 13, "win_pct": 0.385,
                "last_10": "4-0-6", "home_record": "3-0-7", "away_record": "0-0-3",
            },
        ]
    )
    batting = pd.DataFrame(
        [
            {"team_name": "A隊", "at_bats": 400, "runs": 60, "hits": 110, "doubles": 20,
             "triples": 2, "home_runs": 10, "rbi": 55, "stolen_bases": 8, "caught_stealing": 3,
             "walks": 40, "hit_by_pitch": 5, "strikeouts": 80},
            {"team_name": "B隊", "at_bats": 400, "runs": 55, "hits": 100, "doubles": 18,
             "triples": 1, "home_runs": 8, "rbi": 48, "stolen_bases": 6, "caught_stealing": 4,
             "walks": 35, "hit_by_pitch": 4, "strikeouts": 90},
        ]
    )
    pitching = pd.DataFrame(
        [
            {"team_name": "A隊", "wins": 8, "losses": 5, "saves": 3, "holds": 4,
             "innings_pitched_outs": 350, "hits_allowed": 110, "home_runs_allowed": 10,
             "walks": 40, "strikeouts": 90, "runs_allowed": 55, "earned_runs": 50},
            {"team_name": "B隊", "wins": 5, "losses": 8, "saves": 2, "holds": 3,
             "innings_pitched_outs": 350, "hits_allowed": 115, "home_runs_allowed": 12,
             "walks": 45, "strikeouts": 80, "runs_allowed": 60, "earned_runs": 55},
        ]
    )

    ratings = compute_team_power_ratings(standings, batting, pitching)
    result = predict_matchup("A隊", "B隊", ratings)

    assert result is not None
    assert result["home_win_prob"] < 0.95
    assert result["away_win_prob"] > 0.05


def test_predict_upcoming_games_only_predicts_games_without_scores():
    schedule = pd.DataFrame(
        [
            {"game_date": "07/28", "away_team": "弱隊", "home_team": "強隊",
             "away_score": None, "home_score": None, "status": "", "venue": "主場館"},
            {"game_date": "07/27", "away_team": "弱隊", "home_team": "強隊",
             "away_score": 1, "home_score": 5, "status": "已完賽", "venue": "主場館"},
        ]
    )
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())

    predictions = predict_upcoming_games(schedule, ratings)

    assert len(predictions) == 1
    row = predictions.iloc[0]
    assert row["game_date"] == "07/28"
    assert row["home_team"] == "強隊"
    assert row["home_win_prob"] > row["away_win_prob"]
