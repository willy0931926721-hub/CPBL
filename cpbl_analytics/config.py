"""全域設定值：資料來源網址、儲存路徑、HTTP 參數等。

集中放在這裡是為了：當官網改版、換網址、或要調整節流秒數時，
只需要動這一個檔案，不用去每個 scraper 裡面找散落的常數。
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 目錄
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cpbl.db"
# data/latest 底下的檔案「會」進版控（見 .gitignore），是 GitHub Actions 排程
# 爬完之後 commit 回 repo 的「目前最新一份快照」，Streamlit Cloud 部署版的網頁
# 就是讀這裡的檔案，不依賴本機的 sqlite（sqlite 只是本機執行時拿來累積歷史
# 快照用，不會進版控，避免那個檔案在 git 裡越長越大）。
LATEST_DIR = DATA_DIR / "latest"
FIXTURES_DIR = BASE_DIR / "cpbl_analytics" / "tests" / "fixtures"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LATEST_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 資料來源（中華職棒官網）
# ---------------------------------------------------------------------------
# 注意：官網會不定期改版，若欄位對不上，scraper 會直接拋出
# ParsingError 而不是默默塞進錯誤的欄位，方便你第一時間發現改版。
#
# BASE_URL 用不用「www.」這個問題，官網本身兩種寫法都會出現在自己的網頁
# 標題／連結裡，代表兩個變體不一定同時每個路徑都能連得到（常見於网站把其中
# 一個網域設成只轉址首頁，深層路徑反而 404）。scraper/http.py 的 get_html()
# 遇到 404 時，會自動改試「有無 www.」的另一個變體，所以這裡選哪個當預設
# 不是絕對關鍵，但還是選目前看起來比較是「正式」網址的這個。
BASE_URL = "https://www.cpbl.com.tw"

URLS = {
    "standings": f"{BASE_URL}/standings/season",       # 球隊戰績
    "record_all": f"{BASE_URL}/stats/recordall",        # 全記錄查詢（打擊/投手/守備）
    "toplist": f"{BASE_URL}/stats/toplist",              # 單項排行榜
    "schedule": f"{BASE_URL}/schedule",                  # 賽程
    "box": f"{BASE_URL}/box",                            # 成績看板 / 戰報
}

# 目前 CPBL 使用的球隊（可依球季調整；歷史球隊名稱異動見 README）
TEAM_NAMES = [
    "中信兄弟",
    "統一7-ELEVEn獅",
    "樂天桃猿",
    "富邦悍將",
    "台鋼雄鷹",
    "味全龍",
]

# ---------------------------------------------------------------------------
# HTTP 參數
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 15  # 秒
# 用一般瀏覽器慣用的 User-Agent／標頭，而不是誠實表明「我是一支爬蟲」的
# UA 字串。原因：許多網站前面掛的 CDN／WAF（例如 Cloudflare）對於 UA 裡
# 帶有「bot」字樣、或標頭組合看起來不像瀏覽器的請求，會直接擋掉（有些
# 甚至故意回傳 404 而不是 403，讓人以為是網址錯誤）。這裡只是讓請求「看起來
# 像一般瀏覽器」去讀公開的球季數據頁面，不涉及繞過任何登入、付費牆或
# 驗證機制。
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
# 對同一主機兩次請求間至少間隔幾秒，避免對官網造成負擔
MIN_REQUEST_INTERVAL_SECONDS = 1.5
MAX_RETRIES = 3
