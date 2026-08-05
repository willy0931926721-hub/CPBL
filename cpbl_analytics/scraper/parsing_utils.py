"""共用的 HTML 表格解析工具。

核心設計原則（這是整支程式「確保抓到的資料是對的」最重要的一道防線）：

    絕對不要用「第幾欄」去抓資料，永遠用「表頭文字」去對應欄位。

官網改版時最常見的狀況是「欄位順序調換」或「多塞一欄」，如果用位置索引
（row[3], row[4]...）去讀資料，改版後程式不會出錯，但抓到的數字會全部
錯位——這是最危險的錯誤：安靜地產生錯誤資料。

用表頭文字比對的做法，遇到官網改版、表頭消失或改名時，會直接丟出
ParsingError，逼你在第一時間發現「資料源頭已經跟程式預期的不一樣了」，
而不是讓錯的數字流到分析報表裡。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment
from bs4.element import Tag

from cpbl_analytics.scraper.http import ParsingError

_LEADING_RANK_RE = re.compile(r"^\s*(\d+)\s*(.*)$", re.DOTALL)


def split_leading_rank(raw: str) -> tuple[int | None, str]:
    """拆出合併儲存格開頭的排名數字，回傳 (排名, 剩下的文字)。

    官網好幾個頁面（球隊戰績、打者/投手全記錄查詢）都把「排名」跟後面的
    名稱（球隊、或「球隊+球員」）塞進同一個儲存格，用巢狀 <div>／<span>
    並排顯示，get_text() 撈出來的內容形如 "1\\n樂天桃猿" 或
    "1\\n台鋼雄鷹\\n曾子祐"。這裡只負責拆掉最前面的排名數字，剩下的部分
    交給呼叫端依各自頁面的實際結構（一段 vs. 兩段）繼續拆。
    """
    match = _LEADING_RANK_RE.match(raw)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, raw.strip()


def _clean_text(text: str) -> str:
    return text.replace("\xa0", " ").replace("　", " ").strip()


def _raw_snippet(tag: Tag, *, limit: int = 2500) -> str:
    """回傳一個標籤的原始 HTML（截斷，且先把 HTML 註解拿掉），塞進錯誤訊息
    方便直接比對真實結構。

    只看清理過的文字（表頭字串、儲存格文字）有時候看不出問題，例如：
    表頭用 colspan 合併了好幾個實際資料欄位、資料其實是圖片的 alt 文字、
    欄位裡藏著我們沒預期到的巢狀標籤。附上原始 HTML，之後不用再往返
    一次「你重跑一次、我再看 log」，可以直接從這次的錯誤訊息判斷怎麼修。

    先把 <!-- --> 註解拿掉才截斷：官網原始碼裡常常有大段開發者留的說明
    註解（例如欄位命名慣例），這些註解不影響資料結構判讀，但會把截斷長度
    全部吃光，導致真正需要看的資料格反而被截掉、看不到。
    """
    # 重新獨立解析一份，而不是就地在原本的 tag 上動刀——避免任何 bs4
    # 淺拷貝／父節點共享的疑慮意外動到還在使用中的原始解析樹。
    tag_copy = BeautifulSoup(str(tag), "lxml")
    for comment in tag_copy.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    raw = str(tag_copy)
    if len(raw) > limit:
        return raw[:limit] + f"...(截斷，完整長度 {len(raw)} 字元)"
    return raw


@dataclass(frozen=True)
class ColumnSpec:
    """一個欄位的定義。

    header_aliases: 這個欄位在官網上可能出現的表頭文字（列出多個別名，
        因為同一份資料在不同球季/不同頁面上，官網用的字眼不見得完全一樣，
        例如「打擊率」vs「AVG」）。
    field: 對應到內部資料模型要用的欄位名稱。
    required: 若為 True 但找不到任何別名對應的表頭，直接視為解析失敗。
    """

    header_aliases: tuple[str, ...]
    field: str
    required: bool = True


def parse_table(
    html: str,
    *,
    table_selector: str,
    columns: list[ColumnSpec],
    header_row_selector: str = "thead tr, tr:has(th)",
) -> list[dict[str, str]]:
    """把一個 HTML 表格解析成 list[dict]，key 是 ColumnSpec.field。

    Raises:
        ParsingError: 找不到表格、找不到必要表頭、或表格沒有任何資料列。
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(table_selector)
    if table is None:
        raise ParsingError(
            f"找不到表格（selector={table_selector!r}）。"
            "官網結構可能已變更，請更新 table_selector。"
        )

    header_cells = _find_header_cells(table, header_row_selector)
    if not header_cells:
        raise ParsingError(
            "找不到表頭列（<th>），無法確認欄位對應關係。\n"
            f"表格原始 HTML（截斷）：\n{_raw_snippet(table)}"
        )

    header_texts = [_clean_text(c.get_text()) for c in header_cells]
    body_rows = _find_body_rows(table, header_row_selector)

    def _diagnostics() -> str:
        # 分開附上「表頭列」跟「第一列資料」各自的原始 HTML，而不是整個
        # <table> 塞一份截斷長度——欄位很多的表格（例如打者數據表有 30 幾欄）
        # 光表頭列的原始碼就可能塞滿截斷長度，導致真正需要看的資料格反而
        # 被擠掉、看不到。
        header_row_tag = header_cells[0].parent if header_cells else None
        parts = []
        if header_row_tag is not None:
            parts.append(f"表頭列原始 HTML（截斷）：\n{_raw_snippet(header_row_tag, limit=2000)}")
        if body_rows:
            parts.append(f"第一列資料原始 HTML（截斷）：\n{_raw_snippet(body_rows[0], limit=2000)}")
        else:
            parts.append("（表格目前沒有任何資料列）")
        return "\n".join(parts)

    # 建立「表頭文字 -> 欄位索引」的對應。
    #
    # 每個別名都先找「完全相等」的表頭，找不到才退而求其次找「表頭文字
    # 包含這個別名」的——不能反過來（先掃到誰就用誰），否則像 "盜壘" 這種
    # 別名可能會意外先比對到 "盜壘刺" 這個包含它的、但語意完全不同的欄位，
    # 純粹取決於兩個表頭在 DOM 裡誰先出現，而不是誰的語意才是對的。
    index_of_field: dict[str, int] = {}
    for spec in columns:
        found_index = None
        for alias in spec.header_aliases:
            exact_index = next((idx for idx, text in enumerate(header_texts) if text == alias), None)
            if exact_index is not None:
                found_index = exact_index
                break
            partial_index = next((idx for idx, text in enumerate(header_texts) if alias in text), None)
            if partial_index is not None:
                found_index = partial_index
                break
        if found_index is None:
            if spec.required:
                raise ParsingError(
                    f"表格缺少必要欄位「{spec.field}」"
                    f"（預期表頭別名：{spec.header_aliases}，"
                    f"實際表頭：{header_texts}）。官網可能已改版。\n"
                    f"{_diagnostics()}"
                )
            continue
        index_of_field[spec.field] = found_index

    if not body_rows:
        raise ParsingError(
            "表格沒有任何資料列（可能是空賽季、或版面改變）。\n"
            f"表格原始 HTML（截斷）：\n{_raw_snippet(table)}"
        )

    # 安全檢查：如果資料列的儲存格數量「多於」表頭數量，很可能是表頭用了
    # colspan 合併了好幾個實際資料欄位（例如一個「勝-和-敗」表頭底下其實是
    # 3 個獨立的 <td>）。這種情況下用「表頭索引」去對應資料格會整批錯位，
    # 而且不會被上面任何檢查攔到——所以在這裡明確擋下來，而不是讓錯的資料
    # 流出去。
    sample_row = body_rows[0]
    sample_cell_count = len(sample_row.find_all(["td", "th"]))
    if sample_cell_count > len(header_texts):
        raise ParsingError(
            f"資料列的儲存格數量（{sample_cell_count}）比表頭數量（{len(header_texts)}）多，"
            "可能是表頭用 colspan 合併了多個實際欄位，用索引對應會整批錯位，所以先擋下來。\n"
            f"{_diagnostics()}"
        )

    records: list[dict[str, str]] = []
    for row in body_rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        cell_texts = [_clean_text(c.get_text()) for c in cells]
        if len(cell_texts) < len(header_texts):
            # 常見於合併儲存格的分隔列、廣告列等雜訊列，略過。
            continue
        record = {
            field: cell_texts[idx] if idx < len(cell_texts) else ""
            for field, idx in index_of_field.items()
        }
        records.append(record)

    return records


def _find_header_cells(table: Tag, header_row_selector: str) -> list[Tag]:
    thead = table.find("thead")
    if thead is not None:
        ths = thead.find_all("th")
        if ths:
            return ths
    # fallback: 第一列如果全部是 th，也當表頭
    first_row = table.find("tr")
    if first_row is not None:
        ths = first_row.find_all("th")
        if ths:
            return ths
    return []


def _find_body_rows(table: Tag, header_row_selector: str) -> list[Tag]:
    tbody = table.find("tbody")
    rows_container = tbody if tbody is not None else table
    all_rows = rows_container.find_all("tr")
    # 排除表頭列本身（如果 thead 不存在、表頭是表格內第一個 tr）
    body_rows = [r for r in all_rows if not r.find_all("th")]
    return body_rows


def _strip_wrapping_parens(v: str) -> str:
    """去掉數字外層的括號，例如官網「（故四）」欄位底下的值會寫成「（0）」。

    半形/全形括號都處理，因為不同欄位/不同球季看到的是哪一種不一定。
    """
    v = v.strip()
    for open_p, close_p in (("（", "）"), ("(", ")")):
        if v.startswith(open_p) and v.endswith(close_p):
            v = v[len(open_p) : -len(close_p)].strip()
    return v


def to_int(value: str, *, field: str, allow_dash_as_zero: bool = True) -> int:
    v = _strip_wrapping_parens(value.replace(",", "").strip())
    if v in ("", "-", "--") and allow_dash_as_zero:
        return 0
    try:
        return int(v)
    except ValueError as exc:
        raise ParsingError(f"欄位「{field}」的值「{value}」無法轉成整數") from exc


def to_float(value: str, *, field: str, allow_dash_as_zero: bool = True) -> float:
    v = _strip_wrapping_parens(value.replace(",", "").strip())
    if v in ("", "-", "--") and allow_dash_as_zero:
        return 0.0
    try:
        return float(v)
    except ValueError as exc:
        raise ParsingError(f"欄位「{field}」的值「{value}」無法轉成浮點數") from exc
