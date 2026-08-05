import { teamBadgeLabel, teamColor } from "@/lib/teams";
import { cn } from "@/lib/utils";

interface TeamBadgeProps {
  teamName: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZE_MAP = {
  sm: "h-8 w-8 text-[10px]",
  md: "h-11 w-11 text-xs",
  lg: "h-16 w-16 text-sm",
};

/**
 * 球隊徽章：沒有使用真正的球隊隊徽圖檔（球團商標，這個專案沒有取得
 * 授權），改用「球隊色圓底 + 代表字」，風格上比放一個通用棒球圖示更有
 * 辨識度，也完全沒有版權疑慮。
 */
export function TeamBadge({ teamName, size = "md", className }: TeamBadgeProps) {
  const color = teamColor(teamName);
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-semibold text-white",
        SIZE_MAP[size],
        className,
      )}
      style={{
        background: `linear-gradient(160deg, ${color}, ${color}99)`,
        boxShadow: `0 4px 16px -4px ${color}66`,
      }}
    >
      {teamBadgeLabel(teamName)}
    </div>
  );
}
