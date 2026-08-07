"""測試 Streamlit「比賽勝率預測」分頁在真實會遇到的資料情境下不會噴例外。

背景：Streamlit Cloud 上曾經噴出 StreamlitDuplicateElementKey，根因是
`7_比賽勝率預測.py` 用 `f"away_odds_{game['game_date']}_{game['away_team']}_
{game['home_team']}"` 當 number_input 的 key——game_date 目前還沒抓到（永遠
是空字串，見 scraper/schedule.py 的已知限制），同一組對戰組合這個球季常常
會打好幾場（真實 data/latest/schedule.csv 裡同一組對戰最多出現 3 次），
日期缺了之後這幾個欄位組出來的 key 就會撞在一起。修法是改用 enumerate()
給每張卡片一個保證唯一的序號，不要靠可能重複／缺值的業務欄位組 key。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import cpbl_analytics.config as config
import cpbl_analytics.latest_export as latest_export

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PAGE_PATH = str(PROJECT_ROOT / "cpbl_analytics" / "app" / "pages" / "7_比賽勝率預測.py")

STANDINGS_CSV = """rank,team_name,games,wins,losses,ties,win_pct,games_behind,elimination_number,home_record,away_record,last_10,streak
1,強隊,50,30,20,0,0.6,-,-,15-0-10,15-0-10,6-0-4,W1
2,弱隊,50,20,30,0,0.4,-,-,10-0-15,10-0-15,4-0-6,L1
"""
BATTING_CSV = (
    "player_name,team_name,games,at_bats,runs,hits,doubles,triples,home_runs,rbi,"
    "stolen_bases,caught_stealing,sac_bunts,sac_flies,walks,intentional_walks,"
    "hit_by_pitch,strikeouts,double_plays,avg,obp,slg,ops,plate_appearances\n"
)
PITCHING_CSV = (
    "player_name,team_name,games,wins,losses,saves,holds,innings_pitched_outs,"
    "hits_allowed,home_runs_allowed,walks,intentional_walks,hit_by_pitch,strikeouts,"
    "wild_pitches,balks,runs_allowed,earned_runs,era,whip\n"
)
# 這是真正踩到的地雷：日期是空字串、同一組對戰打了 3 場——跟真實
# data/latest/schedule.csv 目前的實際狀況一致（game_date 還沒抓到、球季裡
# 同一組對戰常常重複好幾次）。
DUPLICATE_MATCHUP_SCHEDULE_CSV = """game_date,away_team,home_team,away_score,home_score,status,venue,away_pitcher,home_pitcher
,弱隊,強隊,,,,主場館,,
,弱隊,強隊,,,,主場館,,
,弱隊,強隊,,,,主場館,,
"""


@pytest.fixture
def latest_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "standings.csv").write_text(STANDINGS_CSV, encoding="utf-8")
    (tmp_path / "batting.csv").write_text(BATTING_CSV, encoding="utf-8")
    (tmp_path / "pitching.csv").write_text(PITCHING_CSV, encoding="utf-8")
    (tmp_path / "schedule.csv").write_text(DUPLICATE_MATCHUP_SCHEDULE_CSV, encoding="utf-8")
    # latest_export.load_dataset_csv() 用的是模組層級的 LATEST_DIR 變數，
    # app/utils.py 的 get_* 函式都是透過這幾個函式讀檔，monkeypatch 這裡
    # 就能讓整條讀取路徑指到測試用的暫存目錄，不用動到真正的 data/latest/。
    monkeypatch.setattr(latest_export, "LATEST_DIR", tmp_path)
    monkeypatch.setattr(config, "LATEST_DIR", tmp_path)
    return tmp_path


def test_prediction_page_renders_without_error_when_matchup_repeats_with_no_date(latest_dir):
    at = AppTest.from_file(PAGE_PATH, default_timeout=60)
    at.run()

    assert not at.exception, [str(e) for e in at.exception]


def test_prediction_page_shows_pitcher_unavailable_placeholder(latest_dir):
    # 沒有先發投手資料時，應該顯示「先發投手未定」這種明確的占位文字，
    # 而不是空白或噴錯——這是這次順便補上的功能（見 predictions.py 的
    # 先發投手 ERA 調整），畫面上要看得出來這個欄位目前確實是空的。
    at = AppTest.from_file(PAGE_PATH, default_timeout=60)
    at.run()

    assert not at.exception
    captions = [c.value for c in at.caption]
    assert any("先發投手未定" in c for c in captions)
