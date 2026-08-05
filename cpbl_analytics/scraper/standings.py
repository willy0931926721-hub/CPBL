"""球隊戰績（standings）scraper。

對應官網「本季球隊戰績」頁面（config.URLS["standings"]）。

官網目前的實際表格結構（2026 球季確認過）：
- 第一欄「排名」跟「球隊」是同一個 <th>/<td>，用巢狀 <div> 並排顯示，
  不是兩個獨立欄位，get_text() 撈出來的內容形如 "1\\n樂天桃猿"。
- 沒有分開的「勝」「負」「和」欄位，而是合併成一欄「勝-和-敗」，
  內容格式是 "8-0-5"（8 勝、0 和、5 敗）。
- 後面還有 6 欄是「對某支球隊的對戰戰績」（表頭是對方球隊名稱），
  這是動態欄位（隨球隊數變動），這裡不解析，只取需要的欄位。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from cpbl_analytics.config import URLS
from cpbl_analytics.scraper.http import ParsingError, get_html
from cpbl_analytics.scraper.parsing_utils import ColumnSpec, parse_table, to_float, to_int

TABLE_SELECTOR = "table.standings_tb, table"

COLUMNS = [
    ColumnSpec(("球隊", "隊伍", "排名"), "rank_team_raw"),
    ColumnSpec(("出賽數", "出賽", "已賽"), "games"),
    ColumnSpec(("勝-和-敗",), "wtl_combined", required=False),
    ColumnSpec(("勝", "勝場"), "wins", required=False),
    ColumnSpec(("負", "敗場", "負場"), "losses", required=False),
    ColumnSpec(("和", "和局", "平"), "ties", required=False),
    ColumnSpec(("勝率",), "win_pct"),
    ColumnSpec(("勝差", "GB"), "games_behind", required=False),
    ColumnSpec(("淘汰指數",), "elimination_number", required=False),
    ColumnSpec(("主場戰績",), "home_record", required=False),
    ColumnSpec(("客場戰績",), "away_record", required=False),
    ColumnSpec(("連勝/連敗", "連勝", "連勝(敗)", "連勝/敗"), "streak", required=False),
    ColumnSpec(("近十場戰績", "近十場", "近十戰"), "last_10", required=False),
]

_RANK_TEAM_RE = re.compile(r"^\s*(\d+)\s*(.+?)\s*$", re.DOTALL)


@dataclass
class TeamStanding:
    team_name: str
    games: int
    wins: int
    losses: int
    ties: int
    win_pct: float
    games_behind: str | None
    last_10: str | None
    streak: str | None
    rank: int | None = None
    elimination_number: str | None = None
    home_record: str | None = None
    away_record: str | None = None


def _split_rank_and_team(raw: str) -> tuple[int | None, str]:
    """把合併儲存格的原始文字（例如 "1\\n樂天桃猿"）拆成排名跟球隊名稱。"""
    match = _RANK_TEAM_RE.match(raw)
    if match:
        return int(match.group(1)), match.group(2)
    return None, raw.strip()


def _split_wtl(raw: str, *, field: str = "wtl_combined") -> tuple[int, int, int]:
    """把 "勝-和-敗" 合併欄位（例如 "8-0-5"）拆成 (勝, 和, 敗)。"""
    parts = raw.strip().split("-")
    if len(parts) != 3:
        raise ParsingError(
            f"欄位「{field}」的值「{raw}」不是預期的「勝-和-敗」三段式格式（例如 8-0-5）。"
            "官網可能已改版，請檢查 standings.py 的解析邏輯。"
        )
    wins, ties, losses = (to_int(p, field=field) for p in parts)
    return wins, ties, losses


def fetch_standings(*, html: str | None = None) -> list[TeamStanding]:
    """抓取並解析球隊戰績表。

    Args:
        html: 若提供則直接解析（測試/離線用），否則會發送 HTTP 請求到官網。
    """
    if html is None:
        html = get_html(URLS["standings"])

    rows = parse_table(html, table_selector=TABLE_SELECTOR, columns=COLUMNS)

    standings: list[TeamStanding] = []
    for i, row in enumerate(rows, start=1):
        rank, team_name = _split_rank_and_team(row["rank_team_raw"])

        if row.get("wtl_combined"):
            wins, ties, losses = _split_wtl(row["wtl_combined"])
        else:
            # 保留舊版官網（勝/負/和分開成三欄）的相容路徑。
            wins = to_int(row.get("wins", "0"), field="wins")
            losses = to_int(row.get("losses", "0"), field="losses")
            ties = to_int(row.get("ties", "0"), field="ties")

        games = to_int(row.get("games", "0"), field="games") or (wins + losses + ties)

        win_pct_raw = row["win_pct"].replace("%", "")
        win_pct = to_float(win_pct_raw, field="win_pct")
        if win_pct > 1.0:  # 官網可能寫成 55.6 而不是 .556
            win_pct = win_pct / 100

        standings.append(
            TeamStanding(
                team_name=team_name,
                games=games,
                wins=wins,
                losses=losses,
                ties=ties,
                win_pct=round(win_pct, 3),
                games_behind=row.get("games_behind") or None,
                elimination_number=row.get("elimination_number") or None,
                home_record=row.get("home_record") or None,
                away_record=row.get("away_record") or None,
                last_10=row.get("last_10") or None,
                streak=row.get("streak") or None,
                rank=rank if rank is not None else i,
            )
        )

    if not standings:
        raise ParsingError("解析出的球隊戰績清單為空。")

    return standings
