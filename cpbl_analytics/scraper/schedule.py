"""賽程與戰報 scraper。

官網賽程頁面確認過是 Vue.js 的單頁應用（SPA）：伺服器回來的原始 HTML
只有年份/月份/比賽類型的篩選下拉選單，實際賽程卡片是瀏覽器執行 JavaScript
後才動態塞進畫面，用一般的 requests 拿到的 HTML 永遠是空殼、看不到任何
比賽資料。因此這裡改用 get_rendered_html()（Playwright + headless
Chromium）取得瀏覽器實際渲染完的 DOM，再用跟其他頁面一樣的 CSS selector
方式解析。

官網目前的實際卡片結構（2026 球季，從真實錯誤訊息確認過）：

```html
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
```

- 比賽狀態是外層 `.game` 這個 div 自己的 class（例如 "final"），不是子元素裡的
  獨立欄位；「客隊/主隊」「比分」也都是同一個 class 前綴（team/num）加上
  away/home 兩個修飾字，而不是兩種不同名稱的獨立欄位。
- ⚠️ **日期（game_date）目前還沒找到官網真正的日期標題結構，抓不到**。
  第一版用「class 名稱裡有沒有 date/day」判斷，已經證實是錯的：兩次
  production 執行都抓到一個 class 名稱剛好符合 /date|day/i、但文字內容
  其實是賽程輪次編號（"1"、"2"、"4"...）的元素，不是日曆日期，已經把
  這個判斷拿掉。第二版改成找「內容形狀」看起來像日期的文字（例如
  "8/05" "2026/08/05" "8月5日"），但這一版在 production 上也還是沒找到
  任何符合的文字——代表真正的日期標題可能：(a) 用完全不同的格式呈現
  （例如純數字不帶分隔符、或英文月份縮寫）、(b) 離卡片本身太遠、超出目前
  往前搜尋 50 個元素的範圍、或 (c) 根本不在卡片附近的 DOM，而是另一個
  完全獨立的區塊（例如日期選單本身）。現在找不到符合日期形狀的文字時，
  直接留空（不再猜測），`fetch_schedule` 會在整批比賽都沒有日期時印出
  賽程區塊的原始 HTML 當診斷資訊，下次 GitHub Actions 執行的 log 就會
  帶著這段輸出，不用另外寫診斷腳本手動跑。
- ⚠️ **先發投手（away_pitcher／home_pitcher）目前也還沒對照過官網真實
  HTML**：先用「跟球隊/比分一樣的 away／home 修飾字慣例」去猜
  （`.pitcher.away`／`.pitcher.home`），production 上這個猜測沒有命中
  （所有未開賽比賽的先發投手都是空的）。找不到就讓這兩個欄位維持 None，
  不會讓比賽的其他欄位（球隊、比分、場地）解析跟著失敗；`fetch_schedule`
  同樣會在所有未開賽比賽都抓不到先發投手時，印出第一場未開賽比賽卡片的
  原始 HTML 當診斷資訊。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

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
#   8月5日 / 08月05日
_DATE_SHAPE_RE = re.compile(
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|\d{1,2}[/-]\d{1,2}(?![/-]\d)"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*日"
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


def _find_game_date(card: Tag) -> str:
    """嘗試從卡片以外的地方（往前找最近一個看起來真的像日期的元素）取得比賽日期。

    只用「內容形狀」判斷（_DATE_SHAPE_RE：長得像 2026/08/05、8/05、8月5日
    這種樣式），不看 class 名稱——舊版有一個「class 名稱裡有 date/day 就採用」
    的備援邏輯，實際在兩次 production 執行中都證實是錯的：抓到的文字是
    "1"、"2"、"4"...這種賽程輪次編號，不是日曆日期（class 名稱剛好符合
    /date|day/i，但语意完全是另一件事）。這個備援已經被拿掉，找不到符合
    日期形狀的文字就回傳空字串，寧可留空也不要放一個確定是錯的猜測值
    進去；呼叫端（fetch_schedule）會在整批比賽都找不到日期時印出診斷用的
    原始 HTML，方便下次對照修正，而不是让這個函式自己編一個看起來有內容
    但其實是錯的答案。
    """
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
    if all(g.date == "" for g in games):
        print(
            "⚠️ 賽程頁面所有比賽都沒有抓到日期（_find_game_date 找不到任何"
            "符合日期形狀的文字）。以下是賽程區塊的原始 HTML（截斷），"
            "有助於確認官網真正的日期標題結構長什麼樣子：\n"
            f"{_diagnostic_html_snippet(soup, limit=6000)}"
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
