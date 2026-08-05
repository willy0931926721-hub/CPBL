import { ConfidenceStars } from "@/components/ConfidenceStars";
import { GlassCard } from "@/components/GlassCard";
import { OddsCompare } from "@/components/OddsCompare";
import { ProgressRing } from "@/components/ProgressRing";
import { TeamBadge } from "@/components/TeamBadge";
import { confidenceFromProb, type GamePrediction } from "@/lib/data";
import { teamColor } from "@/lib/teams";

export function PredictionCard({ game }: { game: GamePrediction }) {
  const confidence = confidenceFromProb(game.homeWinProb);

  return (
    <GlassCard className="overflow-hidden">
      <div className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-[var(--color-text-tertiary)]">
            {game.gameDate} 日 · {game.venue ?? "場地未定"}
          </span>
          <ConfidenceStars rating={confidence} size={13} />
        </div>

        <div className="mt-4 flex items-center justify-around">
          <div className="flex flex-col items-center gap-2">
            <TeamBadge teamName={game.awayTeam} size="md" />
            <span className="text-xs text-[var(--color-text-secondary)]">{game.awayTeam}</span>
            <ProgressRing
              value={game.awayWinProb}
              size={92}
              strokeWidth={8}
              color={teamColor(game.awayTeam)}
              label={`${(game.awayWinProb * 100).toFixed(0)}%`}
              sublabel="客場勝率"
            />
          </div>

          <span className="text-[10px] font-semibold text-[var(--color-text-tertiary)]">VS</span>

          <div className="flex flex-col items-center gap-2">
            <TeamBadge teamName={game.homeTeam} size="md" />
            <span className="text-xs text-[var(--color-text-secondary)]">{game.homeTeam}</span>
            <ProgressRing
              value={game.homeWinProb}
              size={92}
              strokeWidth={8}
              color={teamColor(game.homeTeam)}
              label={`${(game.homeWinProb * 100).toFixed(0)}%`}
              sublabel="主場勝率"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-2xl bg-white/[0.03] px-4 py-2 text-[11px] text-[var(--color-text-tertiary)]">
          <span>實力評分 {game.awayPowerRating.toFixed(3)}</span>
          <span>實力評分 {game.homePowerRating.toFixed(3)}</span>
        </div>
      </div>

      <OddsCompare
        awayTeam={game.awayTeam}
        homeTeam={game.homeTeam}
        awayWinProb={game.awayWinProb}
        homeWinProb={game.homeWinProb}
      />
    </GlassCard>
  );
}
