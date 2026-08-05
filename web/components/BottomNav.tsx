"use client";

import { CalendarDays, Home, MoreHorizontal, Sparkles, Trophy } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "首頁", icon: Home },
  { href: "/schedule", label: "賽程", icon: CalendarDays },
  { href: "/predictions", label: "預測", icon: Sparkles },
  { href: "/rankings", label: "排行榜", icon: Trophy },
  { href: "/more", label: "更多", icon: MoreHorizontal },
];

/**
 * 底部浮動玻璃分頁列（Floating Glass Tab Bar）。用 fixed 定位、
 * 加上 pb-safe 避開 iPhone Home Indicator 的安全區域，觸控熱區
 * 維持在 Apple HIG 建議的 44pt 以上。
 */
export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-safe">
      <div className="glass-surface mb-3 flex w-full max-w-md items-stretch justify-between rounded-[28px] px-2 py-2 shadow-[0_8px_32px_rgba(0,0,0,0.4)]">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex min-h-11 flex-1 flex-col items-center justify-center gap-1 rounded-2xl py-1.5 transition-colors",
                active ? "text-white" : "text-[var(--color-text-tertiary)]",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
                  active && "bg-[var(--color-blue)]/20",
                )}
              >
                <Icon size={20} strokeWidth={active ? 2.4 : 2} />
              </div>
              <span className="text-[10px] font-medium">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
