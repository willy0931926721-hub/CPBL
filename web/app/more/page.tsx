import { ExternalLink, Info, ShieldAlert } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { getLastUpdated } from "@/lib/data";

export const metadata = {
  title: "更多 - CPBL AI 數據分析平台",
};

export default function MorePage() {
  const lastUpdated = getLastUpdated();

  return (
    <div className="flex flex-col gap-4 pt-6 pb-4">
      <header className="flex items-center gap-2">
        <Info size={18} className="text-[var(--color-text-secondary)]" />
        <h1 className="text-xl font-semibold">關於本平台</h1>
      </header>

      <GlassCard className="flex flex-col gap-3 p-5 text-sm text-[var(--color-text-secondary)]">
        <p>
          資料來源：中華職棒大聯盟官方網站，每日由 GitHub Actions 排程自動爬取、
          交叉驗證後更新。
        </p>
        <p>
          最近一次資料更新：
          {lastUpdated.scrapedAt
            ? `${lastUpdated.scrapedAt.slice(0, 10)} ${lastUpdated.scrapedAt.slice(11, 16)}`
            : "未知"}
          （UTC）
        </p>
        <a
          href="https://github.com/willy0929716513-debug/cpbl-new"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-[var(--color-blue)]"
        >
          <ExternalLink size={16} />
          原始碼與資料驗證紀錄（GitHub）
        </a>
      </GlassCard>

      <GlassCard className="flex flex-col gap-3 p-5">
        <div className="flex items-center gap-2 text-[var(--color-red)]">
          <ShieldAlert size={16} />
          <span className="text-sm font-semibold">免責聲明</span>
        </div>
        <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
          本平台呈現的機率、實力評分為統計模型估計值，不是內線消息、也不保證比賽結果，
          更不構成任何投注建議。本平台不提供、也不會串接任何博弈網站的賠率。
          若涉及任何形式的投注，請務必透過合法管道進行、注意當地相關法規（例如未成年
          不得參與、非法境外博弈平台的風險），並量力而為。
        </p>
      </GlassCard>
    </div>
  );
}
