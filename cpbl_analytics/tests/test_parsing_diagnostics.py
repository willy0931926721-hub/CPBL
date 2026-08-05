"""測試 parsing_utils.py 新增的診斷/安全機制：

1. colspan 造成「表頭數量 < 資料列儲存格數量」時，要直接擋下來報錯，
   而不是繼續用索引對應（那樣會整批資料錯位卻不會被發現）。
2. 解析失敗時的錯誤訊息裡要附上原始 HTML 片段，方便直接比對官網真實結構，
   不需要再跑一次才能看到。
"""
from __future__ import annotations

import pytest

from cpbl_analytics.scraper.http import ParsingError
from cpbl_analytics.scraper.parsing_utils import ColumnSpec, parse_table

COLUMNS = [
    ColumnSpec(("球員",), "player_name"),
    ColumnSpec(("打數",), "at_bats"),
]


def test_colspan_header_mismatch_raises_with_diagnostics():
    # 表頭只有 2 個 <th>，但下面故意塞一列有 4 個 <td>，模擬「表頭用
    # colspan 合併了實際上是好幾個獨立資料欄位」的狀況。
    html = """
    <table>
      <thead><tr><th>球員</th><th>打數</th></tr></thead>
      <tbody>
        <tr><td>王小明</td><td>10</td><td>2</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with pytest.raises(ParsingError) as exc_info:
        parse_table(html, table_selector="table", columns=COLUMNS)

    message = str(exc_info.value)
    assert "colspan" in message or "儲存格數量" in message
    assert "王小明" in message  # 有把實際資料內容附進錯誤訊息


def test_missing_header_error_includes_raw_html():
    html = """
    <table>
      <thead><tr><th>球員</th></tr></thead>
      <tbody><tr><td>王小明</td></tr></tbody>
    </table>
    """
    with pytest.raises(ParsingError) as exc_info:
        parse_table(html, table_selector="table", columns=COLUMNS)

    message = str(exc_info.value)
    assert "打數" in message  # 缺少的欄位名稱有提到
    assert "<th>球員</th>" in message  # 表頭列原始 HTML 有附上
    assert "王小明" in message  # 第一列資料原始 HTML 也有附上


def test_diagnostics_strip_html_comments_so_real_data_is_not_truncated_away():
    # 官網原始碼常常在表頭裡塞大段開發註解，這些註解不該把截斷長度佔滿、
    # 害真正需要看的欄位資訊被擠掉。
    html = """
    <table>
      <thead><tr>
        <!-- 這是一大段沒有用的開發註解，應該要被拿掉，不要佔用截斷長度 -->
        <th>球員</th>
      </tr></thead>
      <tbody><tr><td>王小明</td></tr></tbody>
    </table>
    """
    with pytest.raises(ParsingError) as exc_info:
        parse_table(html, table_selector="table", columns=COLUMNS)

    message = str(exc_info.value)
    assert "沒有用的開發註解" not in message
    assert "王小明" in message


def test_normal_matching_cell_count_still_works():
    html = """
    <table>
      <thead><tr><th>球員</th><th>打數</th></tr></thead>
      <tbody><tr><td>王小明</td><td>10</td></tr></tbody>
    </table>
    """
    rows = parse_table(html, table_selector="table", columns=COLUMNS)
    assert rows == [{"player_name": "王小明", "at_bats": "10"}]
