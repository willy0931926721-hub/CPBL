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
- 目前還沒找到「日期」在卡片本身以外的什麼地方（賽程頁面很可能是「一個日期
  標題底下放好幾張當天的比賽卡片」，日期只在標題出現一次）。這裡改用「內容
  形狀」（例如 "8/05" "2026/08/05" "8月5日" 這種樣式的文字）去找日期，而不是
  只看 class 名稱裡有沒有 date/day 這幾個字——舊版曾經真的踩到這個問題：
  production 環境裡有某個 class 名稱剛好符合 /date|day/i（例如
  "matchday"／"gameday" 這種跟賽程「第幾輪」有關、但不是日曆日期的元素），
  導致匯出的 game_date 欄位變成 "1"、"2"、"3" 這種連續整數（賽程輪次編號），
  不是真正的比賽日期。用內容形狀判斷比用 class 名稱判斷更不容易撿到「剛好
  名字很像、內容完全不對」的元素，不管官網實際 class 怎麼命名都能用。

⚠️ **先發投手（away_pitcher／home_pitcher）目前是還沒對照過官網真實 HTML
的猜測性寫法**：這個開發環境本身連不到官網（見上面「重要」段落），目前只
對照過「已完賽」比賽卡片的真實結構（上面的 HTML 範例），「未開賽」比賽卡片
長什麼樣子、先發投手欄位用什麼 class／文字標示，還沒有實際錯誤訊息可以參考。
這裡先用「跟球隊/比分一樣的 away／home 修飾字慣例」去猜（`.pitcher.away`／
`.pitcher.home`），找不到就讓這兩個欄位維持 None，不會讓比賽的其他欄位
（球隊、比分、場地、日期）解析跟著失敗。等實際觸發一次 GitHub Actions、
看到「未開賽」比賽卡片的真實 HTML 診斷輸出，才能把這裡改成跟其他 scraper
一樣、有真實結構佐證的精確版本。
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

_DATE_HEADER_RE = re.compile(r"date|day", re.IGNORECASE)

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

    優先用「內容形狀」判斷（_DATE_SHAPE_RE：長得像 2026/08/05、8/05、8月5日
    這種樣式），而不是只看 class 名稱有沒有 date/day 這幾個字——舊版只看
    class 名稱時，曾經在 production 環境真的抓到一個 class 名稱剛好符合
    /date|day/i、但文字內容其實是賽程輪次編號（"1"、"2"、"3"...）的元素，
    導致匯出的日期欄位整批是連續整數而不是日曆日期。往前找最近 50 個元素
    (限制搜尋範圍，避免整頁掃到最上面的導覽列、Log 太慢)，只要文字內容
    符合日期形狀就採用，不管它的 class 叫什麼名字，這樣即使官網實際用的
    class 名稱跟這裡的猜測完全不同，也還是抓得到。

    找不到任何符合日期形狀的元素時，才退回舊版「class 名稱猜測」當最後
    手段；再找不到就回傳空字串，不會因此讓整場比賽的其他資料（球隊、比分）
    也一起解析失敗。
    """
    for el in card.find_all_previous(limit=50):
        text = el.get_text(strip=True)
        if text and len(text) <= 40 and _DATE_SHAPE_RE.search(text):
            return text

    date_like = card.find_previous(attrs={"class": _DATE_HEADER_RE})
    if date_like is not None:
        text = date_like.get_text(strip=True)
        if text:
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

    games: list[GameResult] = []
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

        games.append(
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
            )
        )

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

    return games
