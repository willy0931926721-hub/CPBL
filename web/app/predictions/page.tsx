import { Sparkles } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { PredictionCard } from "@/components/PredictionCard";
import { getPredictions } from "@/lib/data";

export const metadata = {
  title: "AI 預測 - CPBL AI 數據分析平台",
};

export default function PredictionsPage() {
  const predictions = getPredictions();

  return (
    <div className="flex flex-col gap-4 pt-6">
      <header className="flex items-center gap-2">
        <Sparkles size={18} className="text-[var(--color-blue)]" />
        <h1 className="text-xl font-semibold">AI 預測</h1>
      </header>

      <p className="text-xs leading-relaxed text-[var(--color-text-tertiary)]">
        用畢氏勝率期望值、球季戰績、近況、主客場優勢，加上先發投手本季 ERA（找得到的話）
        算出的統計估計值，僅供參考，不保證比賽結果。先發投手資料目前是猜測性寫法，
        找不到時預測仍會照常顯示，只是不包含這項調整。
      </p>

      {predictions.length === 0 ? (
        <GlassCard className="p-5 text-sm text-[var(--color-text-secondary)]">
          目前沒有找到尚未開打、可供預測的比賽。
        </GlassCard>
      ) : (
        <div className="flex flex-col gap-4 pb-4">
          {predictions.map((game, i) => (
            <PredictionCard key={`${game.gameDate}-${game.awayTeam}-${game.homeTeam}-${i}`} game={game} />
          ))}
        </div>
      )}
    </div>
  );
}
