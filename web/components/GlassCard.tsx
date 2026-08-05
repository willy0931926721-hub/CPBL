"use client";

import { motion } from "framer-motion";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  as?: "div";
}

/**
 * 全站共用的玻璃卡片：Rounded 24px、模糊底層背景、淡淡邊框。
 * hover=true 時滑鼠移過去會有輕微上浮動畫（桌機瀏覽時的質感細節，
 * 觸控裝置上這個效果不會有作用，不影響行動裝置體驗）。
 */
export function GlassCard({ children, className, hover = false }: GlassCardProps) {
  return (
    <motion.div
      className={cn("glass-surface rounded-3xl", className)}
      whileHover={hover ? { y: -4, transition: { type: "spring", stiffness: 300, damping: 24 } } : undefined}
    >
      {children}
    </motion.div>
  );
}
