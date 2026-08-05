"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

interface OddsCompareProps {
  awayTeam: string;
  homeTeam: string;
  awayWinProb: number;
  homeWinProb: number;
}

/**
 * 讓使用者輸入自己查到的賠率（歐洲盤格式），算出隱含機率、跟模型預測
 * 機率的落差。這支程式本身完全不提供、也不儲存任何賠率資料——賠率
 * 永遠是使用者自己輸入的暫時狀態，重新整理頁面就會消失。
 */
export function OddsCompare({ awayTeam, homeTeam, awayWinProb, homeWinProb }: OddsCompareProps) {
  const [open, setOpen] = useState(false);
  const [awayOdds, setAwayOdds] = useState(1.9);
  const [homeOdds, setHomeOdds] = useState(1.9);

  const awayImplied = 1 / awayOdds;
  const homeImplied = 1 / homeOdds;
  const awayEdge = awayWinProb - awayImplied;
  const homeEdge = homeWinProb - homeImplied;

  return (
    <div className="border-t border-white/[0.08]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 w-full items-center justify-between px-5 py-3 text-xs text-[var(--color-text-secondary)]"
      >
        輸入你查到的賠率，比對隱含機率
        <ChevronDown size={16} className={cn("transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="flex flex-col gap-4 px-5 pb-5">
          <p className="text-[11px] leading-relaxed text-[var(--color-text-tertiary)]">
            賠率格式：歐洲盤（例如 1.90 代表押 100 元贏 90 元）。隱含機率 = 1 ÷
            賠率；「差距」= 模型預測機率 − 隱含機率，正值代表模型比賠率更看好這隊，
            純供參考，不是投注建議。
          </p>

          <OddsRow
            label={`${awayTeam}（客）`}
            odds={awayOdds}
            onOddsChange={setAwayOdds}
            implied={awayImplied}
            edge={awayEdge}
          />
          <OddsRow
            label={`${homeTeam}（主）`}
            odds={homeOdds}
            onOddsChange={setHomeOdds}
            implied={homeImplied}
            edge={homeEdge}
          />
        </div>
      )}
    </div>
  );
}

function OddsRow({
  label,
  odds,
  onOddsChange,
  implied,
  edge,
}: {
  label: string;
  odds: number;
  onOddsChange: (v: number) => void;
  implied: number;
  edge: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-[var(--color-text-secondary)]">{label}</span>
      <div className="flex items-center justify-between gap-2">
        <input
          type="number"
          min={1.01}
          step={0.01}
          value={odds}
          onChange={(e) => onOddsChange(Number(e.target.value) || 1.01)}
          className="glass-surface h-11 w-20 shrink-0 rounded-xl px-2 text-center text-sm tabular-nums text-white outline-none"
        />
        <span className="flex-1 text-right text-xs tabular-nums text-[var(--color-text-tertiary)]">
          隱含 {(implied * 100).toFixed(0)}%
        </span>
        <span
          className={cn(
            "w-16 shrink-0 text-right text-xs font-semibold tabular-nums",
            edge > 0 ? "text-[var(--color-green)]" : "text-[var(--color-red)]",
          )}
        >
          {edge > 0 ? "+" : ""}
          {(edge * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}
