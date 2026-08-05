// 把 repo 根目錄的 data/latest/（GitHub Actions 排程爬蟲 commit 回來的最新
// 資料快照）複製一份進 web/data/latest/，在 `npm run build`／`npm run dev`
// 之前先跑。
//
// 為什麼要複製一份，而不是直接讓程式碼用相對路徑（../data/latest）讀
// repo 根目錄的檔案：Vercel 這類 serverless 平台在打包 Next.js 的
// production build 時，只會把「專案根目錄（這裡設定的 Root Directory=web/）
// 底下」的檔案追蹤進最終要部署的檔案裡，repo 裡 web/ 目錄以外的檔案不保證
// 在 runtime 時還在——複製到 web/data/latest/ 之後，資料就變成 web/ 這個
// Next.js 專案「自己的」檔案，不用依賴任何跨目錄的檔案追蹤設定，本機開發
// 環境、Vercel 部署都會是同一套邏輯。
//
// web/data/ 本身不進版控（見 web/.gitignore）：真正的資料來源永遠是
// repo 根目錄的 data/latest/，這裡只是建置流程的中繼複製，避免兩份資料
// 各自維護、彼此對不上。
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = join(__dirname, "..", "..", "data", "latest");
const destination = join(__dirname, "..", "data", "latest");

if (!existsSync(source)) {
  console.warn(
    `[copy-data] 找不到 ${source}，略過複製（本機開發時，先跑一次 python -m cpbl_analytics.cli scrape 產生 data/latest/ 快照，或直接從 git 拉取已經 commit 過的版本）。`,
  );
  process.exit(0);
}

mkdirSync(dirname(destination), { recursive: true });
cpSync(source, destination, { recursive: true });
console.log(`[copy-data] 已從 ${source} 複製到 ${destination}`);
