"""測試 get_rendered_html() 在 playwright 沒裝好時，能給出清楚的錯誤訊息。

真的啟動瀏覽器渲染頁面這件事，依賴「本機/CI 環境有沒有裝好對應版本的
Chromium」，不適合放進一般的快速 pytest 套件（會變慢、環境依賴、容易
在不同機器上得到不一致的結果）。這裡改成驗證「找不到 playwright 套件時」
的錯誤處理路徑本身是對的；瀏覽器真的渲染出正確 DOM 這件事，已經在開發
時手動驗證過（用一個內嵌 JS 修改 DOM 的 data: URL 測試，確認
page.content() 回傳的是 JS 執行後的結果，不是原始 HTML）。
"""
from __future__ import annotations

import builtins
from unittest.mock import Mock

import pytest

from cpbl_analytics.scraper.http import (
    FetchError,
    _diagnostic_body_snippet,
    _goto_with_www_fallback,
    _select_and_verify,
    _try_click_button_by_text,
    _try_click_by_text,
    _try_select_option,
    get_rendered_html,
)


def test_get_rendered_html_raises_clear_error_when_playwright_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api" or name.startswith("playwright"):
            raise ImportError("simulated: playwright not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(FetchError, match="playwright"):
        get_rendered_html("https://example.com")


def _fake_response(status: int) -> Mock:
    resp = Mock()
    resp.status = status
    return resp


def test_goto_with_www_fallback_succeeds_on_first_try():
    page = Mock()
    page.goto.return_value = _fake_response(200)

    _goto_with_www_fallback(page, "https://www.cpbl.com.tw/schedule", timeout_ms=1000)

    assert page.goto.call_count == 1


def test_goto_with_www_fallback_retries_non_www_on_404():
    page = Mock()
    page.goto.side_effect = [_fake_response(404), _fake_response(200)]

    _goto_with_www_fallback(page, "https://www.cpbl.com.tw/schedule", timeout_ms=1000)

    assert page.goto.call_count == 2
    called_urls = [call.args[0] for call in page.goto.call_args_list]
    assert called_urls == [
        "https://www.cpbl.com.tw/schedule",
        "https://cpbl.com.tw/schedule",
    ]


def test_goto_with_www_fallback_raises_when_both_variants_fail():
    page = Mock()
    page.goto.side_effect = [_fake_response(404), _fake_response(404)]

    with pytest.raises(FetchError):
        _goto_with_www_fallback(page, "https://www.cpbl.com.tw/schedule", timeout_ms=1000)


def _fake_select(option_texts: list[str]) -> Mock:
    select = Mock()
    option_locator = Mock()
    option_locator.all_inner_texts.return_value = option_texts
    select.locator.return_value = option_locator
    return select


def test_try_select_option_finds_matching_option_and_selects_it():
    page = Mock()
    matching_select = _fake_select(["打者", "投手", "守備"])
    selects = Mock()
    selects.count.return_value = 1
    selects.nth.return_value = matching_select
    page.locator.return_value = selects

    assert _try_select_option(page, "投手") is True
    matching_select.select_option.assert_called_once_with(label="投手")


def test_try_select_option_returns_false_when_no_select_matches():
    page = Mock()
    non_matching_select = _fake_select(["2024", "2025", "2026"])
    selects = Mock()
    selects.count.return_value = 1
    selects.nth.return_value = non_matching_select
    page.locator.return_value = selects

    assert _try_select_option(page, "投手") is False


def test_try_select_option_falls_back_to_substring_match():
    # 官網下拉選單裡實際顯示的文字是「投手成績」，不是單純的「投手」——
    # 這是修這支程式的真正原因，一定要涵蓋這個情境。
    page = Mock()
    select = _fake_select(["打者成績", "投手成績", "守備成績"])
    selects = Mock()
    selects.count.return_value = 1
    selects.nth.return_value = select
    page.locator.return_value = selects

    assert _try_select_option(page, "投手") is True
    select.select_option.assert_called_once_with(label="投手成績")


def test_try_click_by_text_skips_click_when_locator_finds_nothing():
    # 這是修這支程式的關鍵原因：locator 完全沒找到符合的元素時，
    # click() 預設會一直等到逾時，而不是馬上失敗。用 count() 先檔掉，
    # 才不會把整個逾時預算耗在一個註定失敗的策略上。
    page = Mock()
    locator = Mock()
    locator.count.return_value = 0
    page.get_by_text.return_value.first = locator

    assert _try_click_by_text(page, "投手", exact=True) is False
    locator.click.assert_not_called()


def test_try_click_by_text_clicks_when_locator_finds_something():
    page = Mock()
    locator = Mock()
    locator.count.return_value = 1
    page.get_by_text.return_value.first = locator

    assert _try_click_by_text(page, "投手", exact=True) is True
    locator.click.assert_called_once()


def test_try_click_by_text_returns_false_instead_of_raising_when_click_fails():
    # 這次真的在 GitHub Actions 上發生的情況：模糊比對「查詢」意外抓到一個
    # 麵包屑導覽連結「全記錄查詢」，那個元素找得到（count()==1）但點不了
    # （不可見），click() 逾時丟出例外。這個例外不該往上炸，否則後面
    # 「搜尋」「送出」等備用策略、以及最後帶完整診斷的錯誤訊息都不會執行到。
    page = Mock()
    locator = Mock()
    locator.count.return_value = 1
    locator.click.side_effect = TimeoutError("Locator.click: Timeout 3000ms exceeded.")
    page.get_by_text.return_value.first = locator

    assert _try_click_by_text(page, "查詢", exact=False) is False


def test_try_click_button_by_text_prefers_real_button_over_unrelated_text():
    # CPBL 官網真正的查詢按鈕是 <input type="button" value="查詢">，不是
    # <button> 標籤，所以要用 get_by_role("button", ...)（涵蓋 <input
    # type="button"／submit>），不能用 locator("button", ...) 或純文字比對。
    page = Mock()
    button = Mock()
    button.count.return_value = 1
    page.get_by_role.return_value.first = button

    assert _try_click_button_by_text(page, ["查詢", "搜尋"]) is True
    button.click.assert_called_once()


def test_try_click_button_by_text_tries_next_text_when_no_button_matches_first():
    page = Mock()
    no_button = Mock()
    no_button.count.return_value = 0
    yes_button = Mock()
    yes_button.count.return_value = 1

    def get_by_role_side_effect(_role, name=None):
        loc = Mock()
        loc.first = yes_button if name == "搜尋" else no_button
        return loc

    page.get_by_role.side_effect = get_by_role_side_effect

    assert _try_click_button_by_text(page, ["查詢", "搜尋"]) is True
    yes_button.click.assert_called_once()


def test_try_click_button_by_text_returns_false_when_nothing_matches():
    page = Mock()
    no_button = Mock()
    no_button.count.return_value = 0
    page.get_by_role.return_value.first = no_button

    assert _try_click_button_by_text(page, ["查詢", "搜尋", "送出"]) is False


def _page_with_selectable_option(option_texts: list[str]) -> Mock:
    """回傳一個 page mock，其 <select> 選單能被 _try_select_option 選中。

    select 查詢走 page.locator("select")，按鈕查詢走 page.get_by_role("button", ...)
    ——兩條路徑用不同的 mock 方法，本來就不會互相干擾，這裡把「找不到按鈕」
    設成預設值，讓測試專注在 select 這條路徑上。
    """
    page = Mock()
    select = _fake_select(option_texts)
    selects = Mock()
    selects.count.return_value = 1
    selects.nth.return_value = select
    page.locator.return_value = selects

    no_button = Mock()
    no_button.count.return_value = 0
    page.get_by_role.return_value.first = no_button
    return page


def test_select_and_verify_returns_content_immediately_when_no_verification_needed():
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.return_value = "<html>投手資料</html>"

    result = _select_and_verify(
        page, url="https://example.com", option_text="投手成績",
        verify_text_absent=None, timeout_ms=1000,
    )

    assert result == "<html>投手資料</html>"


def test_select_and_verify_clicks_query_button_when_switch_did_not_take_effect():
    # 選完選項後畫面第一次還是舊內容（仍有「打擊率」），程式應該再多按一次
    # 「查詢」按鈕，第二次拿到的內容才是真的切換後的結果。
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.side_effect = ["<html>打擊率...(舊內容)</html>", "<html>防禦率...(新內容)</html>"]

    query_button = Mock()
    query_button.count.return_value = 1
    page.get_by_text.return_value.first = query_button

    result = _select_and_verify(
        page, url="https://example.com", option_text="投手成績",
        verify_text_absent="打擊率", timeout_ms=1000,
    )

    assert result == "<html>防禦率...(新內容)</html>"
    query_button.click.assert_called_once()


def test_select_and_verify_raises_when_stale_content_never_changes():
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.return_value = "<html>打擊率...(還是舊內容)</html>"

    no_button = Mock()
    no_button.count.return_value = 0
    page.get_by_text.return_value.first = no_button

    with pytest.raises(FetchError, match="打擊率"):
        _select_and_verify(
            page, url="https://example.com", option_text="投手成績",
            verify_text_absent="打擊率", timeout_ms=1000,
        )


def test_select_and_verify_accepts_new_content_via_verify_text_present():
    # 這是實際在 GitHub Actions 上踩到的地雷：投手表格自己也有一欄
    # 「被打擊率」，字串裡剛好包含「打擊率」，用 verify_text_absent="打擊率"
    # 判斷「舊內容是否消失」永遠會判定失敗，即使切換其實已經成功。改用
    # verify_text_present 檢查「新內容的專屬標記」（例如投手表才有的
    # 「防禦率」）就不會有這個問題。
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.return_value = "<html>防禦率...被打擊率...(新內容，但仍含「打擊率」子字串)</html>"

    result = _select_and_verify(
        page, url="https://example.com", option_text="投手成績",
        verify_text_absent=None, verify_text_present="防禦率", timeout_ms=1000,
    )

    assert "防禦率" in result


def test_select_and_verify_clicks_query_button_when_expected_marker_missing():
    # 對應 verify_text_present 版本的「需要多按一次查詢按鈕」情境。
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.side_effect = ["<html>打擊率...(舊內容)</html>", "<html>防禦率...(新內容)</html>"]

    query_button = Mock()
    query_button.count.return_value = 1
    page.get_by_text.return_value.first = query_button

    result = _select_and_verify(
        page, url="https://example.com", option_text="投手成績",
        verify_text_absent=None, verify_text_present="防禦率", timeout_ms=1000,
    )

    assert result == "<html>防禦率...(新內容)</html>"
    query_button.click.assert_called_once()


def test_select_and_verify_raises_when_expected_marker_never_appears():
    page = _page_with_selectable_option(["打者成績", "投手成績"])
    page.content.return_value = "<html>打擊率...(還是舊內容)</html>"

    no_button = Mock()
    no_button.count.return_value = 0
    page.get_by_text.return_value.first = no_button

    with pytest.raises(FetchError, match="防禦率"):
        _select_and_verify(
            page, url="https://example.com", option_text="投手成績",
            verify_text_absent=None, verify_text_present="防禦率", timeout_ms=1000,
        )


def test_diagnostic_body_snippet_strips_head_boilerplate_and_keeps_body():
    # 這是修這支程式的實際原因：官網的 <head> 塞了一堆 Google Tag Manager、
    # jQuery 選單套件等追蹤碼／樣式表，光 <head> 就吃光原本 4000 字元的
    # 截斷長度，導致錯誤訊息裡完全看不到 <body> 裡真正需要看的表單/表格內容。
    html = """
    <html><head>
      <script src="https://www.googletagmanager.com/gtm.js?id=GTM-XXXX"></script>
      <style>.foo { color: red; }</style>
      <link href="/theme/client/css/style.css" rel="stylesheet">
      <!-- 一堆開發註解 -->
      <title>全記錄查詢</title>
    </head>
    <body>
      <select><option>打者成績</option><option>投手成績</option></select>
      <table><tr><th>打擊率</th></tr></table>
    </body></html>
    """
    snippet = _diagnostic_body_snippet(html, limit=6000)

    assert "googletagmanager" not in snippet
    assert "color: red" not in snippet
    assert "一堆開發註解" not in snippet
    assert "<select>" in snippet
    assert "投手成績" in snippet


def test_diagnostic_body_snippet_skips_nav_and_finds_main_content():
    # 這是修這支程式的第二次原因：光拿掉 <head> 還不夠，官網 <body> 最前面
    # 整套導覽選單（手機版選單、主選單、球隊 logo 列）本身就有好幾千字元，
    # 一樣會把截斷長度吃光，看不到 #Content 裡真正的表單/表格內容。
    nav_filler = "<li><a href='/x'>雜訊連結</a></li>" * 200
    html = f"""
    <html><body>
    <div class="mm-menu" id="MenuMobile"><ul>{nav_filler}</ul></div>
    <div class="mm-page" id="Wrap">
      <header id="Header">
        <nav id="Menu"><ul>{nav_filler}</ul></nav>
      </header>
      <div id="Center">
        <div id="Content">
          <select><option>打者成績</option><option>投手成績</option></select>
          <table><tr><th>打擊率</th></tr></table>
        </div>
      </div>
    </div>
    </body></html>
    """
    snippet = _diagnostic_body_snippet(html, limit=6000)

    assert "雜訊連結" not in snippet
    assert "<select>" in snippet
    assert "投手成績" in snippet
