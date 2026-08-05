"""打者「全記錄查詢」scraper：抓取球員完整季度打擊數據。

對應官網 config.URLS["record_all"]（打者是這個頁面預設顯示的分頁）。

官網目前的實際表格結構（2026 球季確認過）：
- 第一欄「排名」跟「球員」是同一個儲存格，裡面其實塞了排名／球隊／球員
  三段資訊（球隊用一個指到球隊頁面的連結顯示、球員名字也是另一個連結），
  get_text() 撈出來的內容形如 "1\\n台鋼雄鷹\\n曾子祐"。
- 「（故四）」（故意四壞）這個表頭欄位底下的數值本身也包著括號，
  例如 "（0）"，不是「安打」那種欄位的乾淨數字。
- 「整體攻擊指數」才是這個網頁對 OPS 的稱呼；另外還有一個「OPS+」
  （進階、聯盟平均校正過的版本），跟原始 OPS 是不同的數字，不要混在一起。
"""
from __future__ import annotations

from dataclasses import dataclass

from cpbl_analytics.config import URLS
from cpbl_analytics.scraper.http import ParsingError, get_html
from cpbl_analytics.scraper.parsing_utils import (
    ColumnSpec,
    parse_table,
    split_leading_rank,
    to_float,
    to_int,
)

TABLE_SELECTOR = "table.RecordTable, table.record_table, table"

COLUMNS = [
    ColumnSpec(("球員", "選手", "姓名", "排名"), "rank_team_player_raw"),
    ColumnSpec(("出賽數", "出賽"), "games"),
    ColumnSpec(("打席", "PA"), "plate_appearances", required=False),
    ColumnSpec(("打數", "AB"), "at_bats"),
    ColumnSpec(("得分", "R"), "runs"),
    ColumnSpec(("安打", "H"), "hits"),
    ColumnSpec(("二安", "二壘打", "2B"), "doubles"),
    ColumnSpec(("三安", "三壘打", "3B"), "triples"),
    ColumnSpec(("全壘打", "HR"), "home_runs"),
    ColumnSpec(("打點", "RBI"), "rbi"),
    ColumnSpec(("盜壘刺", "CS"), "caught_stealing", required=False),
    ColumnSpec(("盜壘", "SB"), "stolen_bases", required=False),
    ColumnSpec(("犧短", "犧牲短打", "SH"), "sac_bunts", required=False),
    ColumnSpec(("犧飛", "犧牲高飛", "SF"), "sac_flies", required=False),
    ColumnSpec(("四壞球", "四壞", "BB"), "walks", required=False),
    ColumnSpec(("（故四）", "故意四壞", "敬遠", "IBB"), "intentional_walks", required=False),
    ColumnSpec(("死球", "觸身球", "HBP"), "hit_by_pitch", required=False),
    ColumnSpec(("被三振", "三振", "SO"), "strikeouts", required=False),
    ColumnSpec(("雙殺打", "GDP"), "double_plays", required=False),
    ColumnSpec(("打擊率", "AVG"), "avg"),
    ColumnSpec(("上壘率", "OBP"), "obp", required=False),
    ColumnSpec(("長打率", "SLG"), "slg", required=False),
    ColumnSpec(("整體攻擊指數", "OPS"), "ops", required=False),
    ColumnSpec(("OPS+",), "ops_plus", required=False),
]


@dataclass
class BattingStat:
    player_name: str
    team_name: str
    games: int
    at_bats: int
    runs: int
    hits: int
    doubles: int
    triples: int
    home_runs: int
    rbi: int
    stolen_bases: int
    caught_stealing: int
    sac_bunts: int
    sac_flies: int
    walks: int
    intentional_walks: int
    hit_by_pitch: int
    strikeouts: int
    double_plays: int
    avg: float
    obp: float | None
    slg: float | None
    ops: float | None
    plate_appearances: int | None = None
    rank: int | None = None
    ops_plus: int | None = None


def _split_team_and_player(raw: str) -> tuple[int | None, str, str]:
    """把合併儲存格（例如 "1\\n台鋼雄鷹\\n曾子祐"）拆成 (排名, 球隊, 球員)。

    球隊名稱固定沒有空白字元，球員名字則可能含空白（例如洋將的英文姓名），
    所以拆完排名之後，剩下文字的「第一個詞」當球隊，其餘全部合併回去當
    球員姓名，而不是單純假設剛好兩個詞。
    """
    rank, remainder = split_leading_rank(raw)
    parts = remainder.split()
    if len(parts) < 2:
        raise ParsingError(
            f"無法從合併儲存格「{raw}」拆出球隊與球員名稱"
            "（預期格式是「排名 球隊 球員」，官網可能已改版，請檢查 batting.py 的解析邏輯）。"
        )
    team_name = parts[0]
    player_name = " ".join(parts[1:])
    return rank, team_name, player_name


def fetch_batting_stats(*, html: str | None = None, year: int | None = None) -> list[BattingStat]:
    if html is None:
        params = {"year": year} if year else None
        html = get_html(URLS["record_all"], params=params)

    rows = parse_table(html, table_selector=TABLE_SELECTOR, columns=COLUMNS)

    stats: list[BattingStat] = []
    for row in rows:
        rank, team_name, player_name = _split_team_and_player(row["rank_team_player_raw"])

        def gi(field: str) -> int:
            return to_int(row.get(field, "0"), field=field)

        def gf(field: str) -> float:
            return to_float(row.get(field, "0"), field=field)

        stats.append(
            BattingStat(
                player_name=player_name,
                team_name=team_name,
                rank=rank,
                games=gi("games"),
                at_bats=gi("at_bats"),
                runs=gi("runs"),
                hits=gi("hits"),
                doubles=gi("doubles"),
                triples=gi("triples"),
                home_runs=gi("home_runs"),
                rbi=gi("rbi"),
                stolen_bases=gi("stolen_bases"),
                caught_stealing=gi("caught_stealing"),
                sac_bunts=gi("sac_bunts"),
                sac_flies=gi("sac_flies"),
                walks=gi("walks"),
                intentional_walks=gi("intentional_walks"),
                hit_by_pitch=gi("hit_by_pitch"),
                strikeouts=gi("strikeouts"),
                double_plays=gi("double_plays"),
                avg=gf("avg"),
                obp=gf("obp") if row.get("obp") else None,
                slg=gf("slg") if row.get("slg") else None,
                ops=gf("ops") if row.get("ops") else None,
                plate_appearances=gi("plate_appearances") if row.get("plate_appearances") else None,
                ops_plus=gi("ops_plus") if row.get("ops_plus") else None,
            )
        )

    if not stats:
        raise ParsingError("解析出的打者資料為空。")

    return stats
