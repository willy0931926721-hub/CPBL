import type { Metadata, Viewport } from "next";

import { BottomNav } from "@/components/BottomNav";

import "./globals.css";

export const metadata: Metadata = {
  title: "CPBL AI 數據分析平台",
  description: "中華職棒（CPBL）AI 數據分析、比賽勝率預測與球隊/球員數據平台。",
};

export const viewport: Viewport = {
  themeColor: "#090b10",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant" className="h-full">
      <body className="flex min-h-full flex-col bg-[var(--color-bg)] pt-safe antialiased">
        <div className="mx-auto w-full max-w-md flex-1 px-4 pb-32">{children}</div>
        <BottomNav />
      </body>
    </html>
  );
}
