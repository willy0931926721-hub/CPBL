import { CalendarDays } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { TeamBadge } from "@/components/TeamBadge";
import { getSchedule } from "@/lib/data";
import { cn } from "@/lib/utils";

export const metadata = {
  title: "賽程 - CPBL AI 數據分析平台",
};

export default function SchedulePage() {
  const games = getSchedule();
  const sorted = [...games].reverse();

  return (
    <div className="flex flex-col gap-4 pt-6">
      <header className="flex items-center gap-2">
        <CalendarDays size={18} className="text-[var(--color-blue)]" />
        <h1 className="text-xl font-semibold">賽程與戰報</h1>
      </header>

      {sorted.length === 0 ? (
        <GlassCard className="p-5 text-sm text-[var(--color-text-secondary)]">
          目前沒有賽程資料。
        </GlassCard>
      ) : (
        <div className="flex flex-col gap-3 pb-4">
          {sorted.map((game, i) => {
            const isFinal = game.awayScore !== null && game.homeScore !== null;
            return (
              <GlassCard key={`${game.gameDate}-${game.awayTeam}-${game.homeTeam}-${i}`} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-[var(--color-text-tertiary)]">
                    {game.gameDate} 日 · {game.venue ?? "場地未定"}
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium",
                      isFinal
                        ? "bg-white/[0.06] text-[var(--color-text-secondary)]"
                        : "bg-[var(--color-blue)]/15 text-[var(--color-blue)]",
                    )}
                  >
                    {game.status || (isFinal ? "已完賽" : "未開賽")}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TeamBadge teamName={game.awayTeam} size="sm" />
                    <span className="text-sm">{game.awayTeam}</span>
                  </div>
                  <span className="tabular-nums text-sm font-semibold">{game.awayScore ?? "-"}</span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TeamBadge teamName={game.homeTeam} size="sm" />
                    <span className="text-sm">{game.homeTeam}</span>
                  </div>
                  <span className="tabular-nums text-sm font-semibold">{game.homeScore ?? "-"}</span>
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
