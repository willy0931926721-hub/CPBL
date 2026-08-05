"""測試 schedule.py 對照官網真實卡片結構的解析邏輯（離線 HTML，不連外部網站）。

fixture 裡的卡片結構是從實際爬蟲失敗訊息裡貼出來的真實 HTML 片段直接
比照著寫的（比分/球隊都是 "xxx away"/"xxx home" 這種同一個 class 前綴
加修飾字的寫法，比賽狀態是外層 .game 這個 div 自己的 class）。
"""
from __future__ import annotations

from cpbl_analytics.scraper.schedule import fetch_schedule
from cpbl_analytics.validation import validate_schedule

REAL_STRUCTURE_HTML = """
<html><body>
<div class="game final">
  <a href="/box?year=2026&kindCode=A&gameSno=167">
    <div>
      <div class="info">
        <div class="place"> 亞太主 </div>
        <div class="game_no"> 167 </div>
      </div>
      <div class="vs_box">
        <div class="team away"><span title="樂天桃猿">
            樂天桃猿
        </span></div>
        <div class="score">
          <div class="num away">
            0
          </div>
          <div class="text">:</div>
          <div class="num home">
            1
          </div>
        </div>
        <div class="team home"><span title="統一7-ELEVEn獅">
            統一7-ELEVEn獅
        </span></div>
      </div>
      <div class="remark"><!-- --></div>
    </div>
  </a>
</div>
<div class="game final">
  <a href="/box?year=2026&kindCode=A&gameSno=168">
    <div>
      <div class="info">
        <div class="place"> 台南 </div>
        <div class="game_no"> 168 </div>
      </div>
      <div class="vs_box">
        <div class="team away"><span title="中信兄弟">
            中信兄弟
        </span></div>
        <div class="score">
          <div class="num away">
            5
          </div>
          <div class="text">:</div>
          <div class="num home">
            3
          </div>
        </div>
        <div class="team home"><span title="富邦悍將">
            富邦悍將
        </span></div>
      </div>
    </div>
  </a>
</div>
</body></html>
"""


def test_fetch_schedule_parses_real_card_structure():
    games = fetch_schedule(html=REAL_STRUCTURE_HTML)
    assert len(games) == 2

    first = games[0]
    assert first.away_team == "樂天桃猿"
    assert first.home_team == "統一7-ELEVEn獅"
    assert first.away_score == 0
    assert first.home_score == 1
    assert first.status == "已完賽"
    assert first.venue == "亞太主"
    assert first.is_final is True

    second = games[1]
    assert second.away_team == "中信兄弟"
    assert second.home_team == "富邦悍將"
    assert second.away_score == 5
    assert second.home_score == 3


def test_schedule_validation_passes_on_consistent_sample():
    games = fetch_schedule(html=REAL_STRUCTURE_HTML)
    report = validate_schedule(games)
    assert report.all_passed, [c.message for c in report.checks if not c.passed]


def test_fetch_schedule_leaves_date_and_pitchers_blank_when_not_found():
    # REAL_STRUCTURE_HTML 裡沒有任何看起來像日期的文字、也沒有先發投手相關
    # 元素——這兩個欄位都是「找不到就留空」的最佳猜測，不該讓其他欄位的
    # 解析跟著失敗（見 schedule.py 檔案開頭「重要」段落的說明）。
    games = fetch_schedule(html=REAL_STRUCTURE_HTML)
    assert games[0].date == ""
    assert games[0].away_pitcher is None
    assert games[0].home_pitcher is None


# 這個 fixture 裡的「日期標題」跟「先發投手」結構是根據 schedule.py 目前的
# 猜測性解析邏輯設計的（見該檔案開頭「⚠️」段落的說明），**還沒有對照過官網
# 「未開賽」比賽卡片的真實 HTML**。這個測試只驗證「如果官網真的長這樣，
# 解析邏輯本身是對的」，不保證官網實際上真的是這個結構——那部分要等實際
# 觸發一次 GitHub Actions、看到真實診斷輸出才能確認。
UPCOMING_GAME_WITH_DATE_AND_PITCHERS_HTML = """
<html><body>
<div class="date_title">2026/08/06</div>
<div class="game upcoming">
  <a href="/box?year=2026&kindCode=A&gameSno=170">
    <div>
      <div class="info">
        <div class="place"> 台南 </div>
        <div class="game_no"> 170 </div>
      </div>
      <div class="vs_box">
        <div class="team away"><span title="樂天桃猿">樂天桃猿</span></div>
        <div class="pitcher away">王力威</div>
        <div class="score">
          <div class="num away"></div>
          <div class="text">:</div>
          <div class="num home"></div>
        </div>
        <div class="team home"><span title="中信兄弟">中信兄弟</span></div>
        <div class="pitcher home">陳仕朋</div>
      </div>
    </div>
  </a>
</div>
</body></html>
"""


def test_fetch_schedule_extracts_date_by_content_shape_not_class_name():
    # 這是修過的真實 bug：舊版只看 class 名稱有沒有符合 /date|day/i，
    # production 環境曾經因此誤抓到跟「輪次編號」有關的元素，日期欄位
    # 整批變成 "1"、"2"、"3" 這種連續整數。這裡的 class 名稱
    # （"date_title"）故意符合舊版的判斷條件，用來確認新版是靠「內容形狀」
    # （2026/08/06 這種樣式）挑對元素，而不是純粹因為 class 名稱裡有 "date"。
    games = fetch_schedule(html=UPCOMING_GAME_WITH_DATE_AND_PITCHERS_HTML)
    assert len(games) == 1
    assert games[0].date == "2026/08/06"


def test_fetch_schedule_extracts_starting_pitchers_when_present():
    games = fetch_schedule(html=UPCOMING_GAME_WITH_DATE_AND_PITCHERS_HTML)
    assert len(games) == 1
    game = games[0]
    assert game.away_pitcher == "王力威"
    assert game.home_pitcher == "陳仕朋"
    assert game.away_score is None
    assert game.home_score is None
    assert game.is_final is False
