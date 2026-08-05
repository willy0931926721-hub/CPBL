"""測試 schedule.py 對照官網真實卡片結構的解析邏輯（離線 HTML，不連外部網站）。

fixture 裡的卡片結構是從實際爬蟲失敗訊息裡貼出來的真實 HTML 片段直接
比照著寫的（比分/球隊都是 "xxx away"/"xxx home" 這種同一個 class 前綴
加修飾字的寫法，比賽狀態是外層 .game 這個 div 自己的 class）。
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from cpbl_analytics.scraper.schedule import _game_group_context_snippet, fetch_schedule
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


def test_fetch_schedule_prints_diagnostic_html_when_all_dates_missing(capsys):
    # 這是實際在 production 踩到的情況：兩支球隊、比分都解析對了，但整批
    # 比賽都沒有日期——這種「整批都找不到」通常代表判斷邏輯本身沒對上
    # 官網真實結構，值得印出診斷用的原始 HTML，而不是靜靜留一堆空欄位、
    # 下次還要另外寫診斷腳本才能查。
    fetch_schedule(html=REAL_STRUCTURE_HTML)
    captured = capsys.readouterr()
    assert "所有比賽都沒有抓到日期" in captured.out
    assert "亞太主" in captured.out  # 診斷輸出裡應該包含賽程區塊的原始 HTML




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


def test_fetch_schedule_does_not_print_diagnostics_when_date_and_pitchers_found(capsys):
    # 對照組：日期跟先發投手都有找到時，不該印出「整批都找不到」的診斷
    # 訊息（那是保留給「猜測邏輯本身沒對上官網結構」的情況用的）。
    fetch_schedule(html=UPCOMING_GAME_WITH_DATE_AND_PITCHERS_HTML)
    captured = capsys.readouterr()
    assert "所有比賽都沒有抓到日期" not in captured.out
    assert "沒有抓到先發投手" not in captured.out


def test_fetch_schedule_prints_diagnostic_html_when_all_upcoming_pitchers_missing(capsys):
    # 先發投手抓不到，但日期抓得到——確認兩個診斷是各自獨立觸發的，
    # 不是綁在一起判斷。
    html = UPCOMING_GAME_WITH_DATE_AND_PITCHERS_HTML.replace('class="pitcher away"', 'class="starter away"').replace(
        'class="pitcher home"', 'class="starter home"'
    )
    games = fetch_schedule(html=html)
    assert games[0].away_pitcher is None
    assert games[0].home_pitcher is None

    captured = capsys.readouterr()
    assert "沒有抓到先發投手" in captured.out
    assert "所有比賽都沒有抓到日期" not in captured.out


def test_game_group_context_snippet_walks_up_ancestor_chain_not_guessed_container():
    # 這是實際踩到的地雷：_diagnostic_html_snippet() 用「class 名稱裡有
    # schedule 字樣」去猜容器，production 上真的誤中了搜尋篩選表單
    # （class="ScheduleSearch"，字面符合但語意無關），完全沒有幫助。這裡
    # 確認新版改成「直接照 DOM 結構往上爬固定層數」之後，不會被一個語意
    # 無關、但 class 名稱長得很像的元素誤導——往上爬到的內容應該包含日期
    # 標題（在祖先層級的兄弟元素），而不是完全不相關的篩選表單。
    html = """
    <html><body>
      <div class="ScheduleSearch FormElmt">
        <select><option>2026</option></select>
      </div>
      <div class="day_group">
        <div class="date_title">2026/08/09(日)</div>
        <div class="game">
          <a href="/box?year=2026&kindCode=A&gameSno=246">
            <div>
              <div class="vs_box">
                <div class="team away"><span title="統一7-ELEVEn獅">統一7-ELEVEn獅</span></div>
                <div class="team home"><span title="味全龍">味全龍</span></div>
              </div>
            </div>
          </a>
        </div>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    card = soup.select_one(".game")

    snippet = _game_group_context_snippet(card, ancestor_levels=1)

    assert "2026/08/09" in snippet
    assert "ScheduleSearch" not in snippet


def test_game_group_context_snippet_truncates_long_output():
    html = "<html><body><div>" + ("x" * 20000) + '<div class="game"></div></div></body></html>'
    soup = BeautifulSoup(html, "lxml")
    card = soup.select_one(".game")

    snippet = _game_group_context_snippet(card, ancestor_levels=1, limit=500)

    assert len(snippet) < 1000
    assert "截斷" in snippet


def test_game_group_context_snippet_stops_at_document_root_without_erroring():
    # ancestor_levels 比實際祖先層數還多時，不該爆例外，直接停在最上層。
    html = '<div class="game">just this</div>'
    soup = BeautifulSoup(html, "lxml")
    card = soup.select_one(".game")

    snippet = _game_group_context_snippet(card, ancestor_levels=50)

    assert "just this" in snippet
