"""賽程與戰報 scraper。

官網賽程頁面確認過是 Vue.js 的單頁應用（SPA）：伺服器回來的原始 HTML
只有年份/月份/比賽類型的篩選下拉選單，實際賽程卡片是瀏覽器執行 JavaScript
後才動態塞進畫面，用一般的 requests 拿到的 HTML 永遠是空殼、看不到任何
比賽資料。因此這裡改用 get_rendered_html()（Playwright + headless
Chromium）取得瀏覽器實際渲染完的 DOM，再用跟其他頁面一樣的 CSS selector
方式解析。

官網目前的實際卡片結構（2026 球季，從真實錯誤訊息確認過）：

```html
<!-- 已完賽 -->
<div class="game final">
  <a href="/box?year=2026&kindCode=A&gameSno=167">
    <div>
      <div class="info">
        <div class="place">亞太主</div>
        <div class="game_no">167</div>
      </div>
      <div class="vs_box">
        <div class="team away"><span title="樂天桃猿">樂天桃猿</span></div>
        <div class="score">
          <div class="num away">0</div>
          <div class="text">:</div>
          <div class="num home">1</div>
        </div>
        <div class="team home"><span title="統一7-ELEVEn獅">統一7-ELEVEn獅</span></div>
      </div>
    </div>
  </a>
</div>

<!-- 未開賽（從實際 GitHub Actions 執行的診斷輸出確認，2026-08 球季）-->
<div class="game">
  <a href="/box?year=2026&kindCode=A&gameSno=246">
    <div>
      <div class="info">
        <div class="place">天母</div>
        <div class="game_no">246</div>
      </div>
      <div class="vs_box">
        <div class="team away"><span title="統一7-ELEVEn獅">統一7-ELEVEn獅</span></div>
        <div class="score"><div class="text">VS.</div></div>
        <div class="team home"><span title="味全龍">味全龍</span></div>
      </div>
      <div class="remark">
        <!-- --> <!-- --> <!-- --> <!-- --> <!-- -->
        <div class="time">18:35</div>
      </div>
    </div>
  </a>
</div>
```

賽程頁真正的整體版面（從 2026-08-07 排程執行的診斷輸出第一次確認）是
一個**月曆表格**，不是「一個日期標題底下放好幾張當天卡片」的線性列表：

```html
<table>
  <thead><tr><th>星期一</th>...<th>星期日</th></tr></thead>
  <tbody>
    <tr>
      <!-- 月曆最前面幾格用來補滿週次，顯示上個月的尾巴 -->
      <td class="other_month">
        <div>
          <div class="date" data-date="27">27</div>
          <div><a href="javascript:;">...（沒有比賽的空殼）...</a></div>
        </div>
      </td>
      ...
      <!-- 這個月的第 1 天，這天有 3 場比賽 -->
      <td class="three_games">
        <div>
          <div class="date" data-date="1">1</div>
          <div class="game final">...(第一場)...</div>
          <div class="game final">...(第二場)...</div>
          <div class="game final">...(第三場)...</div>
        </div>
      </td>
    </tr>
    <!-- 之後每個 <tr> 是下一週，<td> 的 data-date 繼續累加 -->
  </tbody>
</table>
```

- 比賽狀態是外層 `.game` 這個 div 自己的 class（例如 "final"；未開賽比賽
  目前看到的是完全沒有額外 class，只有 `"game"` 本身）；「客隊/主隊」都是
  同一個 class 前綴（`team`）加上 away/home 兩個修飾字。已完賽比賽的比分
  是 `.num.away`／`.num.home`；未開賽比賽的 `.score` 底下只有一個
  `<div class="text">VS.</div>`，沒有 `.num` 元素（`away_score`／
  `home_score` 因此正確地維持 None，`.num` 為空這件事本身就是可靠的
  「還沒開賽」訊號，不需要額外判斷）。
- ✅ **日期（game_date）現在抓得到了**：前兩版猜錯的根本原因是誤把這裡當成
  「線性列表 + 獨立日期標題」的結構去找——真正的日期資訊其實一直都在
  卡片所在的月曆儲存格（`<td>`）裡，只是**只有「這個月第幾天」的裸數字**
  （`<div class="date" data-date="1">1</div>`），沒有年、沒有月、也沒有
  任何分隔符號，難怪用「內容形狀找 2026/08/05 這種完整日期文字」永遠找
  不到，第一版誤判成「賽程輪次編號」的那串連續整數（"1","2","3"...）
  其實就是這個裸數字本身，只是當時沒有更多上下文可以判斷它其實是「日期」
  而不是「輪次」。現在改成直接照月曆結構取值（見 `_find_game_date`），
  月/年則用爬蟲執行當下的台北時間推算（月曆版面預設顯示「當月」，已對照
  過真實診斷輸出當時的日期一致）；`<td class="other_month">` 這種補滿
  週次用的相鄰月份儲存格，因為沒辦法可靠判斷究竟是上個月還是下個月，
  仍然保留空字串，不亂猜。內容形狀搜尋（`_DATE_SHAPE_RE`）還留著當最後
  手段的備援，以防月曆結構之後又改版；`_game_group_context_snippet()`
  這個「照 DOM 結構往上爬固定層數」的診斷輸出邏輯也還在，萬一兩種方法
  都找不到日期時，下次排程執行的 log 還是會帶著有用的診斷資訊。
- ⚠️ **先發投手（away_pitcher／home_pitcher）**：從上面「未開賽」的真實
  卡片結構可以看到，官網賽程卡片本身完全沒有先發投手相關文字——`.remark`
  底下除了幾個空的 HTML 註解（很可能是 Vue 模板裡條件渲染、但目前沒有
  資料可顯示的欄位，例如天氣、轉播資訊）跟開賽時間 `.time` 之外沒有其他
  內容。這場是抽樣到的第一場未開賽比賽（照 game_no 推斷應該是最近的
  下一場），仍然完全沒有先發投手資訊，比較可能的解釋是官網要等更接近
  比賽時間才會公布、或這項資訊根本不在賽程卡片這個頁面上（可能要另外找
  別的頁面）。程式維持現狀（找不到就是 None，不影響其他欄位），比賽勝率
  預測在沒有先發投手資料時會自動退回只反映兩隊整體實力；先不再對這個
  selector 做第三次猜測，除非之後有新的線索。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from bs4.element import Tag

from cpbl_analytics.config import URLS
from cpbl_analytics.scraper.http import ParsingError, get_rendered_html

GAME_CARD_SELECTOR = ".game"
TEAM_SELECTOR = ".team"
SCORE_SELECTOR = ".num"
VENUE_SELECTOR = ".place"
PITCHER_SELECTOR = ".pitcher, [class*='pitcher']"

# 目前只實際看過 "final"（已完賽）這個狀態值；其他狀態（例如未開賽、延賽）
# 還沒有實際範例可以對照，遇到未知的 class 就直接顯示原始文字，而不是猜。
STATUS_CLASS_LABELS = {
    "final": "已完賽",
}

# 「看起來像日期」的內容形狀，而不是 class 名稱：
#   2026/08/05、2026-08-05（年/月/日）
#   8/05(三)、8-05（月/日，官網賽程頁常見的簡短寫法，可能還帶星期幾）
#   8月5日 / 08月05日 / 2026年8月5日
_DATE_SHAPE_RE = re.compile(
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|\d{1,2}[/-]\d{1,2}(?![/-]\d)"
    r"|(?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*日"
)


def _diagnostic_html_snippet(soup: BeautifulSoup, *, limit: int = 4000) -> str:
    """找一個「看起來最可能是賽程區塊」的元素，回傳其原始 HTML（截斷）。

    優先找 class/id 名稱裡帶有 schedule/game/box 的元素（大概率就是我們要找
    的容器），找不到就退回整個 <body>。這樣錯誤訊息裡附的原始碼，能直接讓人
    比對出目前正確的 class 名稱該怎麼寫，不用再往返一次「你重跑一次工作流程、
    我再看 log」。
    """
    candidate = soup.find(
        attrs={"class": re.compile(r"schedule|game|box", re.IGNORECASE)}
    ) or soup.find(attrs={"id": re.compile(r"schedule|game|box", re.IGNORECASE)})
    target = candidate if candidate is not None else soup.find("body") or soup
    raw = str(target)
    if len(raw) > limit:
        return raw[:limit] + f"...(截斷，完整長度 {len(raw)} 字元)"
    return raw


def _game_group_context_snippet(card: Tag, *, ancestor_levels: int = 4, limit: int = 8000) -> str:
    """取得某張賽程卡片「往上幾層祖先容器」的原始 HTML，用來找日期標題這種
    不在卡片本身裡、而是跟卡片同一層或更上層的兄弟元素的資訊。

    跟 _diagnostic_html_snippet() 的差異：後者是在「完全沒找到任何卡片」時，
    用「猜官網用了哪個 class 名稱」的方式在整個頁面裡找一個看起來像賽程
    區塊的容器——這個猜測法實際踩到一個地雷：官網搜尋篩選表單的 class 剛好
    叫 `ScheduleSearch`（年份/月份/場地下拉選單），字面上完全符合
    「schedule」這個猜測條件，但語意上跟賽程卡片本身沒有關係，_find_game_date
    真正該找的日期標題完全不在那裡。這裡改成已經有一張真的卡片在手上，
    直接照 DOM 結構本身往上爬固定層數，不用再靠字串比對去猜該找哪個容器
    ——如果日期標題是「同一個日期分組容器裡的某個兄弟元素」這種常見結構，
    爬固定層數的祖先幾乎一定會涵蓋到它。
    """
    target: Tag = card
    for _ in range(ancestor_levels):
        parent = target.parent
        if parent is None or not isinstance(parent, Tag):
            break
        target = parent
    raw = str(target)
    if len(raw) > limit:
        return raw[:limit] + f"...(截斷，完整長度 {len(raw)} 字元)"
    return raw


_TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _find_game_date(card: Tag) -> str:
    """取得比賽日期，回傳 "YYYY-MM-DD" 格式，找不到就回傳空字串。

    2026-08-07 排程執行的真實診斷輸出，第一次讓我們看到官網賽程頁真正的
    版面是一個月曆表格（見檔案開頭的「重要」段落），日期資訊就在卡片所在
    的月曆儲存格（`<td>`）裡的 `<div class="date" data-date="1">1</div>`
    ——只有「這個月第幾天」的裸數字，沒有年、沒有月，這也是前兩版
    （class 名稱猜測、內容形狀搜尋）都找不到「完整日期文字」的真正原因。

    年、月用「爬蟲執行當下的台北時間」推算，這是有實際診斷輸出佐證、但
    還沒有 100% 排除例外情況的假設——官網月曆版面預設顯示的剛好是「當月」
    （已對照過真實診斷輸出當時的日期一致），但還沒確認官網有沒有更明確
    的「目前顯示哪個年月」欄位可以直接讀；如果之後發現在月份交界前後
    算出來的日期不對，代表這個假設需要改成直接讀月份下拉選單目前選中的
    值，而不是繼續假設「當月」。

    `<td class="other_month">` 這種月曆版面補滿週次用的「上個月/下個月」
    儲存格，因為沒辦法可靠判斷究竟是上個月還是下個月，這裡先保留空字串、
    不亂猜——目前觀察到這種儲存格都是已完賽的舊比賽，對「近期賽程勝率
    預測」這個主要使用情境（只關心還沒打的比賽）影響不大。

    找不到卡片所在的 `<td>`、或裡面沒有 `.date` 元素時（例如官網又改版），
    退回舊版「內容形狀」搜尋（_DATE_SHAPE_RE）當最後手段，不要整批比賽的
    其他欄位都跟著解析失敗。
    """
    day_cell = card.find_parent("td")
    if day_cell is not None and "other_month" not in (day_cell.get("class") or []):
        date_div = day_cell.find("div", class_=lambda c: c is not None and "date" in c.split())
        if date_div is not None:
            day_text = (date_div.get("data-date") or date_div.get_text(strip=True)).strip()
            if day_text.isdigit():
                now = datetime.now(_TAIPEI_TZ)
                return f"{now.year:04d}-{now.month:02d}-{int(day_text):02d}"

    for el in card.find_all_previous(limit=50):
        text = el.get_text(strip=True)
        if text and len(text) <= 40 and _DATE_SHAPE_RE.search(text):
            return text
    return ""


def _find_starting_pitchers(card: Tag) -> tuple[str | None, str | None]:
    """嘗試抓出這場比賽主客隊的先發投手姓名（主要對「未開賽」比賽有意義，
    「已完賽」比賽官網通常不再顯示先發投手）。

    ⚠️ 這段解析邏輯目前是猜測性寫法，還沒有機會對照官網「未開賽」比賽卡片
    的真實 HTML（見檔案開頭的說明）。這裡先假設先發投手欄位沿用跟球隊/比分
    一樣的慣例——同一個 class（"pitcher"）用 away/home 修飾字區分主客隊，
    找不到就回傳 (None, None)，不會讓其他欄位的解析跟著失敗。
    """
    away_pitcher: str | None = None
    home_pitcher: str | None = None
    for el in card.select(PITCHER_SELECTOR):
        classes = el.get("class") or []
        text = el.get_text(strip=True)
        if not text:
            continue
        if "away" in classes and away_pitcher is None:
            away_pitcher = text
        elif "home" in classes and home_pitcher is None:
            home_pitcher = text
    return away_pitcher, home_pitcher


def _status_from_classes(card: Tag) -> str:
    classes = card.get("class") or []
    other_classes = [c for c in classes if c != "game"]
    if not other_classes:
        return ""
    return STATUS_CLASS_LABELS.get(other_classes[0], other_classes[0])


@dataclass
class GameResult:
    date: str
    away_team: str
    home_team: str
    away_score: int | None
    home_score: int | None
    status: str
    venue: str | None = None
    # 先發投手：主要對「未開賽」比賽有意義，且目前是猜測性寫法（見
    # _find_starting_pitchers 的說明），找不到就是 None，不影響其他欄位。
    away_pitcher: str | None = None
    home_pitcher: str | None = None

    @property
    def is_final(self) -> bool:
        return self.away_score is not None and self.home_score is not None


def fetch_schedule(*, html: str | None = None) -> list[GameResult]:
    if html is None:
        html = get_rendered_html(URLS["schedule"])

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(GAME_CARD_SELECTOR)
    if not cards:
        raise ParsingError(
            f"找不到任何賽程卡片（selector={GAME_CARD_SELECTOR!r}）。"
            "官網賽程頁版面可能已改版，請更新 schedule.py 裡的 selector 常數。\n"
            f"頁面原始 HTML 片段（截斷，方便直接比對真實 class 名稱）：\n"
            f"{_diagnostic_html_snippet(soup)}"
        )

    # 保留 (card, game) 這對配對，而不是只留 games 這個 list——底下的診斷
    # 邏輯需要「找不到日期／先發投手的那場比賽，原本對應的卡片是哪一個」，
    # 用 games.index(...) 之類的方式反查不可靠（GameResult 是 dataclass，
    # 兩場比賽如果欄位剛好完全一樣，index() 會配對到錯的那個），直接在
    # 迴圈裡就地保留配對關係最簡單可靠。
    games_with_cards: list[tuple[Tag, GameResult]] = []
    for card in cards:
        team_els = card.select(TEAM_SELECTOR)
        score_els = card.select(SCORE_SELECTOR)
        venue_el = card.select_one(VENUE_SELECTOR)

        if len(team_els) < 2:
            # 略過非比賽卡片（例如廣告、休兵日提示）
            continue

        away_score = int(score_els[0].get_text(strip=True)) if len(score_els) > 0 and score_els[0].get_text(strip=True).isdigit() else None
        home_score = int(score_els[1].get_text(strip=True)) if len(score_els) > 1 and score_els[1].get_text(strip=True).isdigit() else None
        away_pitcher, home_pitcher = _find_starting_pitchers(card)

        games_with_cards.append((
            card,
            GameResult(
                date=_find_game_date(card),
                away_team=team_els[0].get_text(strip=True),
                home_team=team_els[1].get_text(strip=True),
                away_score=away_score,
                home_score=home_score,
                status=_status_from_classes(card),
                venue=venue_el.get_text(strip=True) if venue_el else None,
                away_pitcher=away_pitcher,
                home_pitcher=home_pitcher,
            ),
        ))

    games = [g for _, g in games_with_cards]

    if not games:
        first_card_html = str(cards[0])
        if len(first_card_html) > 3000:
            first_card_html = first_card_html[:3000] + f"...(截斷，完整長度 {len(first_card_html)} 字元)"
        raise ParsingError(
            f"用 selector {GAME_CARD_SELECTOR!r} 找到 {len(cards)} 個疑似賽程卡片的元素，"
            f"但每一個裡面符合 TEAM_SELECTOR={TEAM_SELECTOR!r} 的元素都不到 2 個，"
            "所以一場比賽都沒解析出來。可能是 GAME_CARD_SELECTOR 抓到了不相關的元素"
            "（例如篩選用的下拉選單），或是 TEAM_SELECTOR 對不上真正球隊名稱的 class。\n"
            f"第一個疑似卡片的原始 HTML（截斷）：\n{first_card_html}"
        )

    # 日期／先發投手都是「找不到就留空，不讓整批資料解析失敗」的欄位（見
    # _find_game_date／_find_starting_pitchers 的說明），所以這裡不會用
    # ParsingError 擋下整個 scrape。但「整批比賽都找不到」通常代表猜測的
    # 判斷邏輯本身就沒對上官網真實結構，不是單一比賽的個案，值得印出來、
    # 而不是靜靜地留一堆空欄位——下次 GitHub Actions 執行的 log 就會帶著
    # 這段診斷用的原始 HTML，不用另外寫診斷腳本手動跑。
    #
    # 這裡刻意用 _game_group_context_snippet(第一張卡片) 而不是
    # _diagnostic_html_snippet(soup)——後者用「class 名稱裡有 schedule 字樣」
    # 去猜容器，實際執行時真的誤中了搜尋篩選表單（class="ScheduleSearch"，
    # 字面上符合但語意完全無關），沒有提供任何有用的線索。前者直接照 DOM
    # 結構從真正的卡片往上爬固定層數，才可能真的涵蓋到日期標題所在的
    # 兄弟元素。
    if all(g.date == "" for g in games):
        print(
            "⚠️ 賽程頁面所有比賽都沒有抓到日期（_find_game_date 找不到任何"
            "符合日期形狀的文字）。以下是第一張卡片往上幾層祖先容器的原始"
            "HTML（截斷），有助於確認官網真正的日期標題結構長什麼樣子：\n"
            f"{_game_group_context_snippet(games_with_cards[0][0])}"
        )

    upcoming = [(c, g) for c, g in games_with_cards if not g.is_final]
    if upcoming and all(g.away_pitcher is None and g.home_pitcher is None for _, g in upcoming):
        first_upcoming_card, _ = upcoming[0]
        card_html = str(first_upcoming_card)
        if len(card_html) > 4000:
            card_html = card_html[:4000] + f"...(截斷，完整長度 {len(card_html)} 字元)"
        print(
            "⚠️ 賽程頁面所有「未開賽」比賽都沒有抓到先發投手（PITCHER_SELECTOR="
            f"{PITCHER_SELECTOR!r} 在卡片裡找不到任何符合的元素）。以下是第一場"
            "未開賽比賽卡片的原始 HTML，有助於確認先發投手欄位的真正結構：\n"
            f"{card_html}"
        )

    return games
