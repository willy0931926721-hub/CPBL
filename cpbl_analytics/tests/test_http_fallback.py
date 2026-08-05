"""測試 get_html 遇到 404 時，會自動改試「有無 www.」的另一個網址變體。

背景：CPBL 官網曾經出現「www.cpbl.com.tw/xxx 回傳 404，但 cpbl.com.tw/xxx
（或反過來）可以正常連上」的狀況，這支測試確保這個自動切換邏輯本身是對的，
不用每次官網網域寫法變動都要人工除錯。
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from cpbl_analytics.scraper.http import FetchError, _swap_www, get_html


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.cpbl.com.tw/standings/season", "https://cpbl.com.tw/standings/season"),
        ("https://cpbl.com.tw/standings/season", "https://www.cpbl.com.tw/standings/season"),
    ],
)
def test_swap_www(url: str, expected: str):
    assert _swap_www(url) == expected


def _fake_response(status_code: int, text: str = "") -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    resp.apparent_encoding = "utf-8"
    resp.headers = {}  # 真的 dict，讓 `in` 判斷可以正常運作，而不是 Mock 的自動屬性
    return resp


def test_get_html_falls_back_to_non_www_on_404():
    responses = [
        _fake_response(404),
        _fake_response(200, "<html>ok (no www)</html>"),
    ]
    with patch("cpbl_analytics.scraper.http.requests.get", side_effect=responses) as mocked_get:
        html = get_html("https://www.cpbl.com.tw/standings/season")

    assert html == "<html>ok (no www)</html>"
    assert mocked_get.call_count == 2
    called_urls = [call.args[0] for call in mocked_get.call_args_list]
    assert called_urls == [
        "https://www.cpbl.com.tw/standings/season",
        "https://cpbl.com.tw/standings/season",
    ]


def test_get_html_raises_when_both_variants_404():
    # get_html 本身有 @retry（遇到 FetchError 會重試 MAX_RETRIES 次），
    # 每次重試都會再各試一次 www / 非 www，所以用一個「永遠回 404」的
    # callable 當 side_effect，而不是限定次數的固定 list。
    with patch(
        "cpbl_analytics.scraper.http.requests.get",
        side_effect=lambda *a, **kw: _fake_response(404),
    ):
        with pytest.raises(FetchError):
            get_html("https://www.cpbl.com.tw/standings/season")


def test_get_html_returns_directly_when_first_try_succeeds():
    responses = [_fake_response(200, "<html>ok</html>")]
    with patch("cpbl_analytics.scraper.http.requests.get", side_effect=responses) as mocked_get:
        html = get_html("https://www.cpbl.com.tw/standings/season")

    assert html == "<html>ok</html>"
    assert mocked_get.call_count == 1
