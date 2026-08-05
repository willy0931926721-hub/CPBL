import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

interface ConfidenceStarsProps {
  /** 1~5 顆星。 */
  rating: number;
  size?: number;
  className?: string;
}

/** AI 信心等級的星等呈現，用 Lucide 的 Star icon（不用 emoji）。 */
export function ConfidenceStars({ rating, size = 16, className }: ConfidenceStarsProps) {
  const filled = Math.round(Math.min(Math.max(rating, 0), 5));
  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={size}
          className={i < filled ? "fill-[var(--color-orange)] text-[var(--color-orange)]" : "text-white/15"}
        />
      ))}
    </div>
  );
}
