import { Trophy } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { TeamBadge } from "@/components/TeamBadge";
import { getPowerRatings, getStandings } from "@/lib/data";
import { teamColor } from "@/lib/teams";

export const metadata = {
  title: "排行榜 - CPBL AI 數據分析平台",
};

export default function RankingsPage() {
  const standings = getStandings();
  const powerRatings = getPowerRatings();
  const powerByTeam = new Map(powerRatings.map((r) => [r.teamName, r]));
  const maxPowerRating = Math.max(...powerRatings.map((r) => r.powerRating), 0.01);

  return (
    <div className="flex flex-col gap-4 pt-6">
      <header className="flex items-center gap-2">
        <Trophy size={18} className="text-[var(--color-orange)]" />
        <h1 className="text-xl font-semibold">球隊排行榜</h1>
      </header>

      {standings.length === 0 ? (
        <GlassCard className="p-5 text-sm text-[var(--color-text-secondary)]">
          目前沒有球隊戰績資料。
        </GlassCard>
      ) : (
        <GlassCard className="divide-y divide-white/[0.06] overflow-hidden">
          {standings.map((team, i) => {
            const power = powerByTeam.get(team.teamName);
            return (
              <div key={team.teamName} className="flex flex-col gap-2 px-4 py-4">
                <div className="flex items-center gap-3">
                  <span className="w-4 shrink-0 text-center text-sm font-semibold text-[var(--color-text-tertiary)]">
                    {team.rank ?? i + 1}
                  </span>
                  <TeamBadge teamName={team.teamName} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{team.teamName}</p>
                    <p className="text-[11px] text-[var(--color-text-tertiary)]">
                      {team.wins}勝 {team.losses}敗 {team.ties}和
                      {team.streak ? ` · ${team.streak}` : ""}
                      {team.last10 ? ` · 近十場 ${team.last10}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-right text-sm font-semibold tabular-nums">
                    {team.winPct.toFixed(3)}
                  </span>
                </div>

                {power && (
                  <div className="flex items-center gap-2 pl-7">
                    <span className="w-16 shrink-0 text-[10px] text-[var(--color-text-tertiary)]">
                      AI 實力評分
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(power.powerRating / maxPowerRating) * 100}%`,
                          background: teamColor(team.teamName),
                        }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right text-[10px] tabular-nums text-[var(--color-text-tertiary)]">
                      {power.powerRating.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </GlassCard>
      )}

      <p className="pb-4 text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
        AI 實力評分 = 畢氏勝率期望值（50%）+ 球季實際勝率（30%）+ 近十場戰績勝率（20%）的加權平均，
        球季初期樣本數少時會自動往聯盟平均收斂，避免小樣本雜訊被當成真正的實力差距。
      </p>
    </div>
  );
}
