# CPBL AI 數據分析平台（網站）

這是 CPBL-NEW 這個 repo 的 Next.js 網站前端。完整說明（架構、資料從哪裡來、
Vercel 部署步驟、跟 Streamlit 版的關係）請看 repo 根目錄的 [README.md](../README.md#-新版網站next-js部署到-vercel)。

## 本機開發

```bash
npm install
npm run dev
```

開發前需要 `data/latest/` 有資料才看得到內容——`npm run dev` 會自動先跑
`scripts/copy-data.mjs`，把 repo 根目錄的 `data/latest/` 複製一份進來
（這份資料本身已經 `git commit` 在 repo 裡，`git pull` 就會拿到）。
