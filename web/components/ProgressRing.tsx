"use client";

import { motion } from "framer-motion";

interface ProgressRingProps {
  /** 0~1 之間的比例（例如勝率 0.653）。 */
  value: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  trackColor?: string;
  label?: string;
  sublabel?: string;
}

/**
 * 用來呈現勝率／信心指數的圓形進度環，AI 預測頁每張比賽卡片的核心視覺
 * 元件。動畫用 Framer Motion 的 spring，讓進度環「長出來」而不是瞬間出現。
 */
export function ProgressRing({
  value,
  size = 120,
  strokeWidth = 10,
  color = "var(--color-blue)",
  trackColor = "rgba(255,255,255,0.08)",
  label,
  sublabel,
}: ProgressRingProps) {
  const clamped = Math.min(Math.max(value, 0), 1);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - clamped) }}
          transition={{ type: "spring", stiffness: 60, damping: 16 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {label && <span className="text-2xl font-semibold tabular-nums text-[var(--color-text)]">{label}</span>}
        {sublabel && <span className="text-[11px] text-[var(--color-text-secondary)]">{sublabel}</span>}
      </div>
    </div>
  );
}
