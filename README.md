# CPBL-NEW ⚾ 中華職棒數據分析平台

一個以「職業分析師」角度打造的中華職棒（CPBL）數據分析工具：從官網爬取球隊戰績、
打者/投手數據、賽程戰報，做**交叉驗證**確保數字正確，計算進階數據指標（wOBA 近似值、
FIP 近似值、畢氏勝率期望值...）、用 log5 公式算出比賽勝率預測，並提供兩套網頁版介面
瀏覽（見下方「網頁版」章節）：

- **`web/`（Next.js，Apple Sports / ESPN / Sofascore 風格，逐步取代下面這套）**：
  正式對外的網站，Premium／Dark Mode／Glassmorphism 質感，部署在 Vercel。
- **`cpbl_analytics/app/`（Streamlit，過渡期保留）**：功能較完整（打者/投手排行榜、
  球隊比較雷達圖、完整資料驗證報表），在 Next.js 版補齊這些頁面之前先繼續保留、
  繼續能用，之後會完全淘汰。

## ⚠️ 重要：關於資料正確性與目前環境限制

這支程式最重要的設計原則是「**先假設抓到的資料是錯的，直到驗證證明它是對的**」：

- **爬蟲不用位置索引讀欄位，只用表頭文字比對**（`scraper/parsing_utils.py`）。
  官網改版、欄位順序調換時，程式會直接丟出 `ParsingError`，而不是安靜地把資料
  塞進錯的欄位。
- **每一個衍生指標都會重新計算一次來交叉驗證**（`validation.py`）：打擊率、上壘率、
  長打率、OPS、防禦率、WHIP，全部用最基礎的欄位（安打、打數、局數、自責分...）
  重新算過，跟官網顯示的數字比對，對不上就標記為警告或錯誤。
- **所有驗證結果都存進資料庫、攤在網頁版「資料驗證」分頁**，不是只告訴你「爬蟲成功」
  四個字。

**目前開發這支程式所用的沙盒環境本身對外網路被基礎設施層擋掉**，所以每一次
真正對官網結構的修正，都是靠使用者實際觸發 GitHub Actions、把失敗的錯誤訊息
（含官網真實 HTML 片段）貼回來，才確認調整方向是對的——而不是憑空猜測。
目前各資料源的狀態：

- **球隊戰績（standings）**：✅ 已對照官網真實結構修正並確認可用。實際結構是
  「排名/球隊合併成一欄」＋「勝-和-敗合併成一欄（例如 `8-0-5`）」＋額外的
  「淘汰指數」「主場戰績」「客場戰績」欄位，跟原本假設的「勝/負/和分開三欄」
  完全不同，`standings.py` 已經改成解析這個真實格式。
- **打者數據（batting）**：✅ 已對照真實結構修正並確認可用。實際結構是
  「排名/球隊/球員」三段合併在同一個儲存格（球隊是指到球隊頁的連結文字），
  「（故四）」欄位的數值本身也包著括號（例如 `（0）`），「整體攻擊指數」
  才是這個頁面對 OPS 的稱呼（另外還有數值完全不同的「OPS+」）。
- **投手數據（pitching）**：✅ 已對照真實結構修正並確認可用。跟打者共用
  同一個網址（`/stats/recordall`），官網用前端 Vue 元件切換分頁、不會改變
  網址，一般 HTTP 請求永遠只會拿到預設的打者分頁；下拉選單裡「投手」這個
  選項實際顯示文字是「投手成績」（不是單純的「投手」），且選完選項後
  還需要（有時）額外按「查詢」按鈕（真正的按鈕元素是
  `<input type="button" value="查詢">`，要用 `get_by_role("button", ...)`
  才抓得到，純文字比對／`<button>` 標籤比對都找不到它）。另外踩到一個
  容易誤判的地雷：曾經用「打擊率」這個字消失了沒有來判斷切換有沒有生效，
  但投手表格自己也有一欄「被打擊率」（對手打擊率），字串裡剛好包含
  「打擊率」，導致這個檢查永遠判定失敗——即使切換其實已經成功。修正成用
  投手表格專屬的「防禦率」字樣是否「出現」來判斷，而不是判斷某段舊字串
  是否「消失」。表頭順序已確認為：防禦率／出賽數／先發／救援／完投／完封／
  勝場／敗場／救援成功／中繼成功／打席／投球數／投球局數／被安打／被全壘打
  （表格從這裡開始官網回應曾經被截斷，後面幾欄暫沿用推測欄名，之後如果
  驗證出錯會再對照修正）。
- **打者/投手榜單只顯示前 15 名**：⚠️ 已對照過一次真實排程執行結果，問題
  還在。第一版猜測是「每頁筆數」下拉選單，加了 `_try_expand_page_size()`
  嘗試找選項文字是「全部」的 `<select>` 並切過去，但實際執行後
  `batting.csv`／`pitching.csv` 依然剛好各 15 筆——代表這個猜測沒有命中
  （官網要嘛沒有這種下拉選單，要嘛用完全不同的機制分頁，例如「載入更多」
  按鈕、真正的頁碼連結，或根本是另一個完全不同的網址參數）。`cli.py` 會
  在筆數剛好卡在常見分頁預設值時印出警告，但目前還沒有更多診斷資訊可以
  判斷真正的分頁機制長什麼樣子，需要下一輪對照真實榜單頁結構才能修正。
- **賽程與戰報（schedule）**：✅ 球隊、比分、狀態、球場的解析已對照官網
  真實結構確認可用（含「未開賽」比賽卡片：`.score` 底下只有一個
  `<div class="text">VS.</div>`、沒有 `.num` 元素，`away_score`／
  `home_score` 因此正確維持 None）。**比賽日期現在抓得到了**：前兩版
  （class 名稱猜測、內容形狀搜尋）都猜錯的根本原因是誤把賽程頁當成
  「線性列表 + 獨立日期標題」的結構去找，真實診斷輸出第一次確認官網賽程
  頁其實是一個**月曆表格**——`<table>` 的 `<thead>` 是星期一到星期日，
  `<tbody>` 每個 `<tr>` 是一週，每個 `<td>` 是月曆上的一格，格子裡先放
  `<div class="date" data-date="1">1</div>`（只有「這個月第幾天」的裸
  數字，沒有年、沒有月，也沒有任何分隔符號——難怪第二版找「2026/08/05」
  這種完整日期文字永遠找不到，第一版誤判成「賽程輪次編號」的那串連續
  整數其實就是這個裸數字本身）才接著放這一天的所有比賽卡片。已經改成
  直接照月曆結構取值，月/年用爬蟲執行當下的台北時間推算（月曆版面預設
  顯示「當月」，已對照過真實診斷輸出當時的日期一致）；`<td class=
  "other_month">` 這種補滿週次用的相鄰月份儲存格，沒辦法可靠判斷究竟是
  上個月還是下個月，仍然保留空字串不亂猜。**先發投手（`away_pitcher`／
  `home_pitcher`）目前確認官網賽程卡片本身沒有這項資訊**：拿抽樣到的下
  一場未開賽比賽真實 HTML 對照過，`.remark` 底下除了幾個空的 Vue 條件
  渲染註解跟開賽時間之外沒有任何先發投手相關文字，比較可能是官網要等更
  接近比賽時間才公布、或這項資訊根本不在這個頁面上。程式維持「找不到就
  是 None、不影響其他欄位」，比賽勝率預測（見下面「比賽勝率預測」章節）
  在抓不到先發投手時會自動退回「只反映兩隊整體實力」，不會因此整個失敗。

**換句話說：程式的「邏輯正確性」（表頭比對、交叉驗證公式）已經過測試證明，
但「跟官網目前實際結構是否完全吻合」是逐一對照真實錯誤訊息修正出來的，
上面列的狀態就是目前的進度。**這正是為什麼「資料驗證」是網頁版的第一等
公民分頁，而不是事後才加的除錯工具——遇到還沒修好的資料源，這裡會清楚
告訴你哪裡不對，而不是安靜地顯示錯誤或缺漏的資料。

## 🚀 全自動雲端版（推薦：不用自己開電腦，資料自動更新）

整套流程設計成「爬蟲跑在 GitHub 的雲端伺服器上、網頁也部署在雲端」，你只需要
**設定一次**，之後資料就會自動更新，完全不需要再打開自己的電腦：

```
GitHub Actions（排程，每天自動跑）
   └─ 執行 cli scrape → 驗證 → 匯出 data/latest/*.csv + validation_summary.json
        └─ 自動 commit 回這個 repo
             └─ Streamlit Community Cloud 偵測到 repo 有新的 commit
                  └─ 自動重新讀取最新資料，網頁跟著更新
```

### 設定步驟（只需要做一次）

**1. 打開 repo 的 Actions 寫入權限**（讓排程爬蟲抓完資料後，能把結果 commit 回 repo）

前往 GitHub 上這個 repo → `Settings` → 左側 `Actions` → `General` → 拉到最下面
`Workflow permissions` → 選 **`Read and write permissions`** → `Save`。這是
GitHub 的預設安全限制，只有你（repo 擁有者）能改，我這邊沒有權限幫你點。

**2. 手動觸發一次爬蟲，確認整條流程沒問題**

repo 上方 `Actions` 分頁 → 左側選 **「定期更新 CPBL 資料」** → 右上角
**`Run workflow`** 按鈕 → 直接按下去。等 1~2 分鐘，工作列表會出現一個綠色打勾
（代表成功、資料已經 commit 回 repo）或紅色叉叉（代表失敗，通常是官網結構
跟程式預期的不一樣，點進去看 log，或參考下面「常見問題」）。

之後這個 workflow 會照 `.github/workflows/scrape.yml` 裡設定的排程
（預設每天台北時間凌晨 4 點）自動執行，你也隨時可以回到 Actions 分頁按
`Run workflow` 立刻手動更新一次，**全程不用開自己的電腦、不用裝 Python**。

**3. 部署網頁版到 Streamlit Community Cloud**（免費，直接連 GitHub repo）

1. 開 https://share.streamlit.io，用你的 GitHub 帳號登入
2. 「New app」→ Repository 選這個 repo、Branch 選 `main`
3. Main file path 填：`cpbl_analytics/app/Home.py`
4. 按 Deploy，等一兩分鐘會拿到一個公開網址（例如 `xxx.streamlit.app`），
   之後這個網址就是你平常看數據用的網頁

部署好之後，**每次 GitHub Actions 排程跑完、把新資料 commit 回 repo，
Streamlit Cloud 會自動偵測到並重新整理**，網頁上的資料就會自動更新，
不需要你手動重新部署，也不需要重新輸入網址。

### 之後的日常使用

- 平常就是直接開那個 `xxx.streamlit.app` 網址看資料，跟開一般網站一樣。
- 想馬上要最新資料、不想等排程時間到：去 GitHub 的 Actions 分頁按一次
  `Run workflow`，等它跑完（1~2 分鐘）網頁就會有新資料。
- 想改自動更新的頻率（例如改成一天兩次、或改成每週一次）：編輯
  `.github/workflows/scrape.yml` 裡 `cron: "0 20 * * *"` 這一行即可
  （cron 語法是「分 時 日 月 星期」，目前設定是 UTC 20:00 = 台北時間隔天 04:00）。
- 想知道最新一次資料到底有沒有通過驗證：網頁版左側「資料驗證」分頁，
  或直接在 GitHub 上打開 `data/latest/validation_summary.json` 這個檔案看。

## 🎨 新版網站（Next.js，部署到 Vercel）

`web/` 目錄是全新設計的正式對外網站，走 Apple Sports／ESPN／Sofascore／
TradingView 那種 Premium、Dark Mode、Glassmorphism 質感，**刻意不做成一般
運彩網站的花俏霓虹風格**。目前做好的頁面：首頁（今日 AI 精選推薦＋近期賽程）、
賽程、AI 預測（勝率 Progress Ring＋可自行輸入賠率比對）、排行榜、更多
（資料來源／免責聲明）。球隊頁、球員頁、AI 分析文章、我的收藏這幾頁還沒做，
先用 Streamlit 版頂著。

### 資料從哪裡來

跟 Streamlit 版共用同一份 `data/latest/`，不會兩邊資料對不上：

```
GitHub Actions（跟 Streamlit 版用同一個排程）
   └─ cli scrape → 匯出 data/latest/*.csv、predictions.json、power_ratings.json
        └─ commit 回這個 repo
             └─ Vercel 偵測到 repo 有新的 commit，重新建置
                  └─ web/scripts/copy-data.mjs 先把 data/latest/ 複製進 web/data/latest/
                       └─ Next.js 用複製過來的這份資料產生新的靜態頁面
```

`predictions.json`／`power_ratings.json` 是 `cpbl_analytics/predictions.py`
（log5 公式＋貝氏小樣本收斂）算好才輸出的——勝率預測的邏輯永遠只有 Python
這一份，Next.js 只負責呈現，不會重新用 TypeScript 兜一次公式、兩邊對不上。

### 部署步驟（只需要做一次）

1. 開 https://vercel.com，用你的 GitHub 帳號登入
2. 「Add New...」→「Project」→ Import 這個 repo
3. **Root Directory 設定成 `web`**（這是最容易漏掉的一步——這個 repo 是
   monorepo，Python 爬蟲跟 Next.js 網站放在同一個 repo，不設定的話 Vercel
   會在 repo 根目錄找 `package.json`，找不到就會部署失敗）
4. Framework Preset 選 Next.js（設好 Root Directory 後通常會自動偵測到）
5. 按 Deploy，等一兩分鐘會拿到一個 `xxx.vercel.app` 網址

部署好之後，跟 Streamlit Cloud 一樣，**每次 GitHub Actions 排程跑完、
commit 新資料回 repo，Vercel 會自動偵測到並重新建置**，不需要手動重新部署。

### 本機開發

```bash
cd web
npm install
npm run dev
```

`npm run dev`／`npm run build` 之前都會先自動跑 `scripts/copy-data.mjs`
把 repo 根目錄的 `data/latest/` 複製一份進來，本機沒有這份資料的話，先在
repo 根目錄跑一次 `python -m cpbl_analytics.cli scrape`（需要能連外網），
或直接 `git pull` 拉最新版（`data/latest/` 本身有進版控）。

## 本機開發 / 除錯用（Streamlit 過渡版，進階）

如果你想在自己電腦上跑（例如要修改 `schedule.py` 裡的 CSS selector、
或想在本機先測試），流程如下：

```bash
# 1. 安裝相依套件
pip install -r requirements.txt

# 1b. 賽程頁是 JS 動態渲染，需要額外裝一次 Playwright 的瀏覽器（只需裝一次）
playwright install chromium

# 2. 先跑測試，確認 parser / 驗證邏輯本身沒問題（不需要網路）
pytest cpbl_analytics/tests -v

# 3. 在「有網路」的環境，實際對官網跑一次爬蟲 + 驗證 + 寫入資料庫，並匯出 data/latest/ 快照
python -m cpbl_analytics.cli scrape --year 2026

# 4. 啟動網頁版
streamlit run cpbl_analytics/app/Home.py
```

啟動後開啟瀏覽器 `http://localhost:8501`，左側導覽列可切換：

| 分頁 | 內容 |
|---|---|
| Home | 總覽、關鍵指標卡片 |
| 球隊戰績 | 戰績表、勝率長條圖、畢氏勝率期望值（實際 vs 理論） |
| 打者排行榜 | 完整打擊數據、可依球隊/最低打數篩選、進階指標（wOBA近似/ISO/BB%/K%）、Top 10 |
| 投手排行榜 | 完整投球數據、進階指標（FIP近似/K-9/BB-9）、Top 10 |
| 球隊比較 | 任選 2+ 支球隊，雷達圖 + 詳細數據對照 |
| 賽程與戰報 | 近期賽果 |
| **資料驗證** | 每次爬蟲執行的完整交叉驗證結果，判斷資料是否可信的依據 |

## 專案結構

```
.github/workflows/scrape.yml   # GitHub Actions 排程：定期跑爬蟲、commit 最新快照
cpbl_analytics/
├── config.py              # 資料來源網址、HTTP 參數等全域設定
├── validation.py          # 資料驗證：交叉檢查所有衍生指標與邏輯一致性
├── sabermetrics.py         # 進階數據：wOBA/FIP 近似值、畢氏勝率、球隊加總
├── storage.py              # SQLite 儲存層（本機用，累積歷史快照，不進版控）
├── latest_export.py         # 匯出/讀取 data/latest/ 的 CSV+JSON（會進版控，雲端版靠這個）
├── cli.py                  # 命令列工具：一鍵爬蟲 + 驗證 + 寫入資料庫 + 匯出快照
├── scraper/
│   ├── http.py              # 共用 HTTP 存取層：節流、重試、例外型別
│   ├── parsing_utils.py     # 表格解析核心：用表頭文字而非欄位位置比對
│   ├── standings.py         # 球隊戰績 scraper
│   ├── batting.py           # 打者「全記錄查詢」scraper
│   ├── pitching.py          # 投手「全記錄查詢」scraper（含 12.1 局數記號正確轉換）
│   └── schedule.py          # 賽程與戰報 scraper
├── predictions.py           # 比賽勝率預測：球隊實力評分 + log5 公式 + 小樣本收斂
├── app/                     # Streamlit 過渡版（見上面「新版網站」章節，逐步淘汰中）
│   ├── Home.py               # Streamlit 入口頁
│   ├── utils.py              # 網頁版共用工具：資料載入（CSV 優先、sqlite 備援）、配色
│   └── pages/                # Streamlit 多頁面（左側導覽列自動產生）
└── tests/
    ├── fixtures/              # 離線測試用的模擬官網 HTML
    ├── test_scraper_parsing.py
    ├── test_validation.py
    ├── test_sabermetrics.py
    ├── test_predictions.py
    └── test_latest_export.py

web/                          # 新版網站（Next.js，部署到 Vercel，見上面「新版網站」章節）
├── app/
│   ├── page.tsx               # 首頁
│   ├── predictions/page.tsx   # AI 預測
│   ├── rankings/page.tsx      # 排行榜
│   ├── schedule/page.tsx      # 賽程
│   └── more/page.tsx          # 更多（資料來源／免責聲明）
├── components/                # GlassCard／ProgressRing／TeamBadge／BottomNav 等共用元件
├── lib/
│   ├── data.ts                 # 讀取 web/data/latest/ 的 CSV／JSON
│   └── teams.ts                # 球隊色票／徽章文字（跟 Python 那邊用同一組色票）
└── scripts/copy-data.mjs       # build/dev 前把 repo 根目錄 data/latest/ 複製進來
```

## 資料怎麼存、怎麼讀（兩層設計）

1. **`data/latest/`（會進版控，雲端版靠這個）**：每次 `cli scrape` 跑完，
   只保留「最新一次」的快照，匯出成體積小、對 git 友善的 CSV
   （`standings.csv` / `batting.csv` / `pitching.csv` / `schedule.csv`）
   跟一份 `validation_summary.json`。GitHub Actions 排程爬完就是把這幾個
   檔案 commit 回 repo；網頁版（不管本機還是 Streamlit Cloud）都優先讀這裡。
   因為檔案小、內容一目了然，你也可以直接在 GitHub 網頁上點開這些檔案看。
2. **`data/cpbl.db`（本機用，已加進 `.gitignore`，不會進版控）**：SQLite
   資料庫，每次執行 `cli scrape` 會新增一批帶時間戳記的完整歷史快照
   （而不是覆蓋），方便在本機做「戰績隨球季變化」之類的歷史趨勢分析。
   刻意不進版控，是因為這個檔案會隨時間無限累積、不適合放進 git 歷史。

## 進階指標的計算方式與已知近似

- **wOBA 近似值**：採用 Tom Tango《The Book》公開的簡化權重，**未依 CPBL 逐年
  得分環境校正**，適合球員間相對排序，不建議直接跟 MLB 官方 wOBA 數值比較絕對大小。
- **FIP 近似值**：採用常見預設常數 3.10，嚴謹分析應改用該球季 CPBL 聯盟平均
  防禦率反推專屬常數。
- **畢氏勝率期望值**：Bill James 公式，指數採 Pythagenpat 常見的 1.83，
  球隊得失分則是加總自 `batting_stats.runs`（得分）與 `pitching_stats.runs_allowed`
  （投手被得分），理論上等同官方球隊得失分。

## 比賽勝率預測（`predictions.py` / 網頁版「比賽勝率預測」分頁）

用畢氏勝率期望值、球季實際勝率、近十場戰績、主客場優勢，算出每支球隊的
「實力評分」，再用 log5 公式（Bill James）換算成任兩隊對戰的單場勝率；
找得到這場比賽的先發投手時，還會再疊加一個先發投手 ERA 調整（見下方
「先發投手調整」）。方法論細節、每個係數為什麼這樣設計，都寫在
`predictions.py` 檔案開頭的 docstring 裡，這裡只列重點：

- **不會、也不打算自動化串接任何博弈網站的賠率**。中華職棒合法的賠率
  來源只有政府特許的台灣運動彩券，其賠率頁面本身需要會員登入、也有
  反爬蟲保護；「玩運彩」這類第三方資訊網站雖然公開瀏覽，但同樣有反
  爬蟲機制擋下直接存取，也沒有明確確認過服務條款是否允許自動化抓取。
  網頁版分頁提供一個「你自己輸入賠率」的小工具，計算隱含機率、跟預測
  機率的落差，但賠率數字永遠要你自己從合法管道查詢後手動輸入。
- **球季初期的小樣本收斂（shrinkage）**：實際測試發現，球季初期（例如
  只打了 13~14 場）任何一項指標的樣本數都還太小，尤其是主客場戰績——
  像「0 勝 0 和 3 敗」這種只有 3 場的客場成績，字面上是 0% 客場勝率，
  直接拿來算 log5 會得出 99%/1% 這種不合理的極端預測。現在每一項指標
  組成 power_rating／主客場優勢調整時，都會依樣本數（場次）往聯盟平均
  收斂，場次越少、越把數字拉回中性值。網頁版表格呈現的仍然是原始、
  沒收斂過的數字，收斂只發生在會影響預測機率的計算內部。
- **先發投手調整**：如果賽程資料裡有這場比賽的先發投手姓名（見
  `scraper/schedule.py` 的 `away_pitcher`/`home_pitcher`，⚠️ 目前是猜測性
  寫法，見上面「重要」段落的說明），會拿這位投手本季 ERA 跟「局數加權」
  的聯盟平均 ERA 比較，ERA 比聯盟平均低就對他所在的球隊加分、反之扣分，
  換算成一個小幅度（預設封頂 ±8 個百分點）的勝率微調——刻意做得保守，
  因為單場比賽同時取決於牛棚、打線手感、守備等這裡完全沒建模的因素，
  先發投手 ERA 也依投球局數做小樣本收斂（球季初期只投幾局的投手，字面上
  的 ERA 不可信）。找不到先發投手姓名、或姓名跟已抓到的投手數據對不上時，
  這個調整量就是 0，預測仍然只反映兩隊整體實力，不會讓整場預測失敗。
  網頁版「AI 預測」分頁會在每張預測卡片上標註日期、場地、雙方先發投手
  姓名與 ERA。

## 已完成的驗證

```
pytest cpbl_analytics/tests -v
# 98 passed
```

涵蓋：表頭比對解析（含官網改版模擬情境會正確拋出錯誤）、colspan 造成表頭/
資料列儲存格數量不一致時會直接擋下來（而不是錯位賦值）、投手局數記號
（`12.1` = 12又1/3局）正確轉換、打擊率/上壘率/長打率/OPS/防禦率/WHIP 交叉驗證、
www / 非 www 網址自動切換邏輯、log5 勝率預測與小樣本收斂、以及故意塞入矛盾
數據（如安打數超過打數）確認驗證機制真的抓得到問題。

Streamlit 網頁版亦已用 `streamlit.testing.v1.AppTest` 對全部 8 個頁面做過
無例外執行測試（包含模擬「全新雲端部署、完全沒有本機 sqlite、只有
`data/latest/` CSV」的情境），並用瀏覽器截圖確認實際版面（表格、圖表、
篩選器、雷達圖）正常渲染。Next.js 新版網站則用 `npm run build` 確認 TypeScript
型別檢查與靜態頁面產生都沒有問題，並用瀏覽器截圖（含 iPhone 尺寸的 mobile
viewport）確認首頁／賽程／AI 預測／排行榜／更多這幾頁的實際版面與互動
（例如 AI 預測頁「輸入賠率比對」的即時計算）都正常運作。

## 常見問題

**Q: GitHub Actions 的「定期更新 CPBL 資料」跑出紅色叉叉（失敗）**
點進那次執行的 log 看是哪一步失敗：
- 如果訊息是 `回傳狀態碼 404`：`scraper/http.py` 已經會自動在
  `www.cpbl.com.tw` / `cpbl.com.tw`（有無 www.）兩種網址間自動切換一次，
  如果兩種都 404，可能有兩種原因：(1) 官網真的把這個頁面路徑改掉了，
  (2) 官網前面的 CDN／WAF 把來自雲端（GitHub Actions／Streamlit Cloud）
  的請求當成機器人擋掉，回傳假的 404 而不是真正的 404 頁面——這種錯誤
  訊息現在會附上回應標頭（`cf-ray` 等）跟一小段回應內容，把完整訊息貼給我
  就能判斷是哪一種，不需要自己判斷。如果真的是被 WAF 擋（IP 層級封鎖，
  不是欄位或程式問題），代表這個資料來源可能沒辦法完全自動化，需要考慮
  改成人工不定期在本機執行、或改抓其他不擋雲端 IP 的資料來源。
- 如果是「執行爬蟲與資料驗證」這步失敗且訊息是 `ParsingError`，代表官網
  改版、欄位表頭或賽程頁 CSS selector 跟程式預期的對不上，需要更新
  `cpbl_analytics/scraper/` 裡對應的檔案（見上面「已知限制」）。這種錯誤
  訊息會直接附上「實際表頭」跟「一小段原始 HTML」，把完整錯誤訊息複製
  貼給我就能直接修，不需要自己動手改程式碼。
- 如果是「提交更新後的資料快照」這步失敗，通常是 Settings → Actions →
  General → Workflow permissions 還沒設成 `Read and write permissions`
  （見「全自動雲端版」設定步驟第 1 步）。

**Q: Streamlit Cloud 上的網頁一直顯示「尚未有資料」**
代表 GitHub Actions 還沒成功執行過一次。去 repo 的 Actions 分頁確認
「定期更新 CPBL 資料」是否至少成功跑過一次（綠色打勾），沒有的話手動按
`Run workflow` 觸發一次。

**Q: 想指定不同球季年度**
`.github/workflows/scrape.yml` 裡 `run: python -m cpbl_analytics.cli scrape`
可以加上 `--year 2025` 之類的參數。

**Q: 想調整自動更新頻率**
編輯 `.github/workflows/scrape.yml` 裡的 `cron` 那一行即可，不需要碰任何
Python 程式碼。

## 免責聲明

本工具僅供個人研究與數據分析使用，請遵守中華職棒官網的服務條款，並注意
`config.py` 中的 `MIN_REQUEST_INTERVAL_SECONDS` 節流設定，不要對官網發送
過於頻繁的請求。

「比賽勝率預測」分頁呈現的機率是統計估計值，不是內線消息、也不保證比賽
結果，更不構成任何投注建議；本工具不提供、也不會串接任何博弈網站的賠率。
若涉及任何形式的投注，請務必透過合法管道進行、注意當地相關法規（例如
未成年不得參與、非法境外博弈平台的風險），並量力而為。
