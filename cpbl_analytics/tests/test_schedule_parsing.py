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
