"use client";

import { animate, useMotionValue, useTransform } from "framer-motion";
import { useEffect } from "react";
import { motion } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

/**
 * 數字滾動動畫：頁面出現時從 0 滾動到實際數值，用在勝率百分比、
 * 實力評分這類「一眼就要抓住注意力」的關鍵數字上。
 */
export function AnimatedNumber({ value, decimals = 0, suffix = "", className }: AnimatedNumberProps) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) => `${v.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.8, ease: [0.16, 1, 0.3, 1] });
    return controls.stop;
  }, [value, motionValue]);

  return <motion.span className={className}>{rounded}</motion.span>;
}
