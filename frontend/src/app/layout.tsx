import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PPT 素材库",
  description: "面向 PPT 页级素材检索、理解、管理与复用的平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
