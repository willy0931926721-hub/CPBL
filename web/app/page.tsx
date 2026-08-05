import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { ConfidenceStars } from "@/components/ConfidenceStars";
import { GlassCard } from "@/components/GlassCard";
import { TeamBadge } from "@/components/TeamBadge";
import { confidenceFromProb, getLastUpdated, getPredictions, getStandings } from "@/lib/data";

export default function HomePage() {
  const predictions = getPredictions();
  const standings = getStandings();
  const lastUpdated = getLastUpdated();

  const topPick = [...predictions].sort(
    (a, b) => Math.abs(b.homeWinProb - 0.5) - Math.abs(a.homeWinProb - 0.5),
  )[0];
  const upcoming = predictions.slice(0, 6);
  const leader = standings[0];

  return (
    <div className="flex flex-col gap-6 pt-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium tracking-wide text-[var(--color-text-tertiary)]">
            CPBL AI ANALYTICS
          </p>
          <h1 className="text-2xl font-semibold">中華職棒數據平台</h1>
        </div>
        {lastUpdated.scrapedAt && (
          <span className="text-[10px] text-[var(--color-text-tertiary)]">
            資料更新 {lastUpdated.scrapedAt.slice(0, 10)}
          </span>
        )}
      </header>

      {topPick ? (
        <Link href="/predictions">
          <GlassCard hover className="relative overflow-hidden p-5">
            <div
              className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full opacity-30 blur-3xl"
              style={{ background: "var(--color-blue)" }}
            />
            <div className="relative flex items-center gap-2 text-[var(--color-blue)]">
              <Sparkles size={16} />
              <span className="text-xs font-semibold tracking-wide">今日 AI 精選推薦</span>
            </div>

            <div className="relative mt-4 flex items-center justify-between">
              <div className="flex flex-col items-center gap-2">
                <TeamBadge teamName={topPick.awayTeam} size="lg" />
                <span className="text-sm font-medium">{topPick.awayTeam}</span>
                <span className="text-lg font-semibold tabular-nums text-[var(--color-text-secondary)]">
                  <AnimatedNumber value={topPick.awayWinProb * 100} decimals={0} suffix="%" />
                </span>
              </div>

              <span className="text-xs text-[var(--color-text-tertiary)]">VS</span>

              <div className="flex flex-col items-center gap-2">
                <TeamBadge teamName={topPick.homeTeam} size="lg" />
                <span className="text-sm font-medium">{topPick.homeTeam}</span>
                <span className="text-lg font-semibold tabular-nums text-[var(--color-blue)]">
                  <AnimatedNumber value={topPick.homeWinProb * 100} decimals={0} suffix="%" />
                </span>
              </div>
            </div>

            <div className="relative mt-4 flex items-center justify-between border-t border-white/[0.08] pt-3">
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">AI 信心等級</span>
                <ConfidenceStars rating={confidenceFromProb(topPick.homeWinProb)} />
              </div>
              <div className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
                查看完整分析 <ArrowRight size={14} />
              </div>
            </div>
          </GlassCard>
        </Link>
      ) : (
        <GlassCard className="p-5 text-sm text-[var(--color-text-secondary)]">
          目前沒有找到尚未開打的比賽可供預測。
        </GlassCard>
      )}

      {leader && (
        <div className="grid grid-cols-2 gap-3">
          <GlassCard className="flex flex-col gap-1 p-4">
            <span className="text-[10px] text-[var(--color-text-tertiary)]">戰績龍頭</span>
            <span className="text-base font-semibold">{leader.teamName}</span>
            <span className="text-xs text-[var(--color-text-secondary)]">
              勝率 {leader.winPct.toFixed(3)}
            </span>
          </GlassCard>
          <GlassCard className="flex flex-col gap-1 p-4">
            <span className="text-[10px] text-[var(--color-text-tertiary)]">收錄比賽數</span>
            <span className="text-base font-semibold tabular-nums">
              <AnimatedNumber value={predictions.length} />
            </span>
            <span className="text-xs text-[var(--color-text-secondary)]">場尚未開打</span>
          </GlassCard>
        </div>
      )}

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--color-text-secondary)]">近期賽程</h2>
          <Link href="/schedule" className="text-xs text-[var(--color-blue)]">
            查看全部
          </Link>
        </div>

        <div className="flex flex-col gap-3">
          {upcoming.length === 0 && (
            <GlassCard className="p-4 text-sm text-[var(--color-text-secondary)]">
              目前沒有即將開打的比賽資料。
            </GlassCard>
          )}
          {upcoming.map((game, i) => (
            <GlassCard key={`${game.gameDate}-${game.awayTeam}-${game.homeTeam}-${i}`} className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">
                  {game.gameDate} 日 · {game.venue ?? "場地未定"}
                </span>
                <ConfidenceStars rating={confidenceFromProb(game.homeWinProb)} size={11} />
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TeamBadge teamName={game.awayTeam} size="sm" />
                  <span className="text-sm">{game.awayTeam}</span>
                </div>
                <span className="tabular-nums text-sm font-semibold text-[var(--color-text-secondary)]">
                  {(game.awayWinProb * 100).toFixed(0)}%
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TeamBadge teamName={game.homeTeam} size="sm" />
                  <span className="text-sm">{game.homeTeam}</span>
                </div>
                <span className="tabular-nums text-sm font-semibold text-[var(--color-blue)]">
                  {(game.homeWinProb * 100).toFixed(0)}%
                </span>
              </div>
            </GlassCard>
          ))}
        </div>
      </section>

      <p className="pb-4 text-center text-[10px] leading-relaxed text-[var(--color-text-tertiary)]">
        呈現的機率為統計模型估計值，非內線消息，不構成投注建議。
        <br />
        本平台不提供、也不串接任何博弈網站的賠率。
      </p>
    </div>
  );
}
