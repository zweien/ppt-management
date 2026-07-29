"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/search", label: "搜索首页", icon: "🔍" },
  { href: "/files", label: "文件管理", icon: "📁" },
  { href: "/pages", label: "页面浏览", icon: "🖼️" },
  { href: "/tags", label: "标签管理", icon: "🏷️" },
  { href: "/favorites", label: "我的收藏", icon: "⭐" },
  { href: "/models", label: "模型配置", icon: "🤖" },
  { href: "/jobs", label: "任务中心", icon: "⚙️" },
  { href: "/trash", label: "回收站", icon: "🗑️" },
];

export default function AppShell({ children, title }: { children: React.ReactNode; title?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<{ username: string } | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("user");
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    if (raw) setUser(JSON.parse(raw));
  }, [router]);

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.replace("/login");
  }

  if (!user) return null;

  return (
    <div className="min-h-screen flex bg-[#f5f7fa]">
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <span className="text-2xl">📊</span>
            <span className="font-bold text-brand-700">PPT 素材库</span>
          </div>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition ${
                  active
                    ? "bg-brand-500 text-white font-medium"
                    : "text-gray-600 hover:bg-brand-50 hover:text-brand-700"
                }`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="px-3 py-3 border-t border-gray-100">
          <div className="text-xs text-gray-400 px-2 mb-2">已登录:{user.username}</div>
          <button
            onClick={logout}
            className="w-full text-sm text-gray-500 hover:text-red-500 px-3 py-1.5 text-left"
          >
            退出登录
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        {title && (
          <header className="px-8 py-5 bg-white border-b border-gray-200">
            <h1 className="text-xl font-semibold text-gray-800">{title}</h1>
          </header>
        )}
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
