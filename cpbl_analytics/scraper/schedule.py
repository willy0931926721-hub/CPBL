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
  標題底下放好幾張當天的比賽卡片」，日期只在標題出現一次）。這裡先嘗試往前
  找最近一個看起來像日期標題的元素，找不到就留空，不會因此讓整批資料解析失敗。
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

# 目前只實際看過 "final"（已完賽）這個狀態值；其他狀態（例如未開賽、延賽）
# 還沒有實際範例可以對照，遇到未知的 class 就直接顯示原始文字，而不是猜。
STATUS_CLASS_LABELS = {
    "final": "已完賽",
}

_DATE_HEADER_RE = re.compile(r"date|day", re.IGNORECASE)


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
    """嘗試從卡片以外的地方（往前找最近一個像日期標題的元素）取得比賽日期。

    這是「盡量找、找不到也沒關係」的最佳猜測：目前還沒確認官網真正的日期
    標題結構，找不到就回傳空字串，不會讓整場比賽的其他資料（球隊、比分）
    也一起解析失敗。
    """
    date_like = card.find_previous(attrs={"class": _DATE_HEADER_RE})
    if date_like is not None:
        text = date_like.get_text(strip=True)
        if text:
            return text
    return ""


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

        games.append(
            GameResult(
                date=_find_game_date(card),
                away_team=team_els[0].get_text(strip=True),
                home_team=team_els[1].get_text(strip=True),
                away_score=away_score,
                home_score=home_score,
                status=_status_from_classes(card),
                venue=venue_el.get_text(strip=True) if venue_el else None,
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
