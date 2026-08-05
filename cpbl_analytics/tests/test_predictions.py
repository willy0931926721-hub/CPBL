"""測試 predictions.py 的勝率預測邏輯（用人工設計的 DataFrame，不連外部網站）。"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from cpbl_analytics.predictions import (
    MAX_PITCHER_EDGE,
    _league_avg_era,
    _pitcher_edge,
    _pitcher_lookup,
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
    # 沒提供 pitching_df 時，先發投手欄位都應該是 None，而不是讓整個函式出錯。
    assert row["home_pitcher"] is None
    assert row["home_pitcher_era"] is None


def _sample_starters_pitching() -> pd.DataFrame:
    """三位投手，用來測先發投手 ERA 調整；「era」欄位刻意跟 earned_runs／
    innings_pitched_outs 保持一致（自責分 * 27 / 出局數），因為
    _league_avg_era() 是拿這兩個基礎欄位重算聯盟平均，「era」欄位若跟它們
    對不上，測試斷言會失去意義（這也是 validate_pitching_stats 本來就會
    交叉驗證、擋下來的那種不一致）。
    """
    cols = ["player_name", "team_name", "era", "earned_runs", "innings_pitched_outs"]
    rows = [
        # 王牌：ERA 明顯低於聯盟平均，局數足夠（60 局），不該被小樣本收斂拉太多。
        {"player_name": "王牌投手", "team_name": "強隊", "era": 3.00,
         "earned_runs": 20, "innings_pitched_outs": 180},
        # 菜鳥：只投了 3 局就自責分掛蛋，ERA 字面上 0.00，但樣本太小應該被收斂。
        {"player_name": "菜鳥投手", "team_name": "強隊", "era": 0.00,
         "earned_runs": 0, "innings_pitched_outs": 9},
        # 爛投手：ERA 明顯高於聯盟平均，局數也足夠。
        {"player_name": "爛投手", "team_name": "弱隊", "era": 10.50,
         "earned_runs": 35, "innings_pitched_outs": 90},
    ]
    return pd.DataFrame(rows, columns=cols)


def test_pitcher_lookup_maps_name_to_era_and_innings_pitched():
    lookup = _pitcher_lookup(_sample_starters_pitching())
    assert lookup["王牌投手"] == (pytest.approx(3.00), pytest.approx(60.0))
    assert lookup["爛投手"] == (pytest.approx(10.50), pytest.approx(30.0))


def test_pitcher_lookup_empty_for_empty_dataframe():
    assert _pitcher_lookup(pd.DataFrame()) == {}


def test_league_avg_era_is_innings_weighted():
    # 用「自責分總和 / 局數總和」重算，而不是把每個投手的 ERA 直接算術平均。
    league_avg = _league_avg_era(_sample_starters_pitching())
    total_er = 20 + 0 + 35
    total_outs = 180 + 9 + 90
    assert league_avg == pytest.approx(total_er * 27 / total_outs)


def test_pitcher_edge_is_zero_without_enough_information():
    lookup = _pitcher_lookup(_sample_starters_pitching())
    assert _pitcher_edge(None, pitcher_lookup=lookup, league_avg_era=4.0) == 0.0
    assert _pitcher_edge("沒聽過的投手", pitcher_lookup=lookup, league_avg_era=4.0) == 0.0
    assert _pitcher_edge("王牌投手", pitcher_lookup=lookup, league_avg_era=None) == 0.0


def test_pitcher_edge_favors_below_average_era_and_penalizes_above_average():
    lookup = _pitcher_lookup(_sample_starters_pitching())
    league_avg = _league_avg_era(_sample_starters_pitching())

    ace_edge = _pitcher_edge("王牌投手", pitcher_lookup=lookup, league_avg_era=league_avg)
    scrub_edge = _pitcher_edge("爛投手", pitcher_lookup=lookup, league_avg_era=league_avg)

    assert ace_edge > 0
    assert scrub_edge < 0
    assert abs(ace_edge) <= MAX_PITCHER_EDGE
    assert abs(scrub_edge) <= MAX_PITCHER_EDGE


def test_pitcher_edge_shrinks_small_sample_era_toward_league_average():
    # 「菜鳥投手」字面上 ERA=0.00（比王牌投手還好），但只投了 3 局，
    # 收斂之後的優勢應該明顯小於局數足夠的王牌投手，而不是比王牌投手更強。
    lookup = _pitcher_lookup(_sample_starters_pitching())
    league_avg = _league_avg_era(_sample_starters_pitching())

    ace_edge = _pitcher_edge("王牌投手", pitcher_lookup=lookup, league_avg_era=league_avg)
    rookie_edge = _pitcher_edge("菜鳥投手", pitcher_lookup=lookup, league_avg_era=league_avg)

    assert 0 < rookie_edge < ace_edge


def test_predict_matchup_with_pitcher_info_favors_team_with_better_starter():
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    pitching = _sample_starters_pitching()
    lookup = _pitcher_lookup(pitching)
    league_avg = _league_avg_era(pitching)

    # 主客隊對調（弱隊主場對強隊），但弱隊派出王牌投手、強隊派出爛投手，
    # 先發投手調整應該至少削弱強隊原本的優勢（即使不足以整個逆轉）。
    baseline = predict_matchup("弱隊", "強隊", ratings)
    with_pitchers = predict_matchup(
        "弱隊", "強隊", ratings,
        home_pitcher="王牌投手", away_pitcher="爛投手",
        pitcher_lookup=lookup, league_avg_era=league_avg,
    )

    assert baseline is not None and with_pitchers is not None
    assert with_pitchers["home_win_prob"] > baseline["home_win_prob"]
    assert with_pitchers["home_pitcher_era"] == pytest.approx(3.00)
    assert with_pitchers["away_pitcher_era"] == pytest.approx(10.50)


def test_predict_matchup_pitcher_fields_are_none_when_not_provided():
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    result = predict_matchup("強隊", "弱隊", ratings)
    assert result is not None
    assert result["home_pitcher"] is None
    assert result["home_pitcher_era"] is None
    assert result["away_pitcher"] is None
    assert result["away_pitcher_era"] is None


def test_predict_upcoming_games_includes_starting_pitcher_era():
    schedule = pd.DataFrame(
        [
            {"game_date": "07/28", "away_team": "弱隊", "home_team": "強隊",
             "away_score": None, "home_score": None, "status": "", "venue": "主場館",
             "away_pitcher": "爛投手", "home_pitcher": "王牌投手"},
        ]
    )
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())
    pitching = _sample_starters_pitching()

    predictions = predict_upcoming_games(schedule, ratings, pitching)

    assert len(predictions) == 1
    row = predictions.iloc[0]
    assert row["home_pitcher"] == "王牌投手"
    assert row["home_pitcher_era"] == pytest.approx(3.00)
    assert row["away_pitcher"] == "爛投手"
    assert row["away_pitcher_era"] == pytest.approx(10.50)


def test_predict_upcoming_games_handles_missing_pitcher_columns_gracefully():
    # 賽程資料裡完全沒有 away_pitcher/home_pitcher 欄位時（例如舊版快照），
    # 不應該讓整個預測流程出錯，只是沒有先發投手調整。
    schedule = pd.DataFrame(
        [
            {"game_date": "07/28", "away_team": "弱隊", "home_team": "強隊",
             "away_score": None, "home_score": None, "status": "", "venue": "主場館"},
        ]
    )
    ratings = compute_team_power_ratings(_sample_standings(), _sample_batting(), _sample_pitching())

    predictions = predict_upcoming_games(schedule, ratings, _sample_starters_pitching())

    assert len(predictions) == 1
    assert predictions.iloc[0]["home_pitcher"] is None
