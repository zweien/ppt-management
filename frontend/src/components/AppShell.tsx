"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Search,
  FileText,
  Images,
  Tag,
  Star,
  Cpu,
  ListChecks,
  Trash2,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { fetchVersion } from "@/lib/version";
import ThemeToggle from "./ThemeToggle";

// Grouped navigation — Vercel-style IA (eyebrow section labels).
const NAV_GROUPS: { label: string; items: { href: string; label: string; icon: React.ComponentType<{ className?: string }> }[] }[] = [
  {
    label: "资源",
    items: [
      { href: "/search", label: "搜索", icon: Search },
      { href: "/files", label: "文件管理", icon: FileText },
      { href: "/pages", label: "页面浏览", icon: Images },
    ],
  },
  {
    label: "整理",
    items: [
      { href: "/tags", label: "标签管理", icon: Tag },
      { href: "/favorites", label: "我的收藏", icon: Star },
    ],
  },
  {
    label: "系统",
    items: [
      { href: "/models", label: "模型配置", icon: Cpu },
      { href: "/jobs", label: "任务中心", icon: ListChecks },
      { href: "/trash", label: "回收站", icon: Trash2 },
    ],
  },
];

export default function AppShell({ children, title }: { children: React.ReactNode; title?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<{ username: string } | null>(null);
  const [version, setVersion] = useState("");

  useEffect(() => {
    const raw = localStorage.getItem("user");
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    if (raw) setUser(JSON.parse(raw));
    fetchVersion().then(setVersion);
  }, [router]);

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.replace("/login");
  }

  if (!user) return null;

  return (
    <div className="min-h-screen flex bg-canvas-soft">
      <aside className="w-64 shrink-0 bg-canvas border-r border-hairline flex flex-col">
        {/* Brand */}
        <div className="px-5 h-16 flex items-center gap-2.5 border-b border-hairline">
          <span className="w-7 h-7 rounded-sm bg-mesh border border-hairline shrink-0" />
          <span className="font-semibold text-ink tracking-tight tracking-display2">PPT 素材库</span>
        </div>

        {/* Grouped nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="px-2 mb-1.5 text-[11px] font-mono uppercase tracking-wider text-mute">
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || pathname?.startsWith(item.href + "/");
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "relative flex items-center gap-2.5 px-3 h-9 rounded-md text-sm transition",
                        active
                          ? "bg-canvas-soft-2 text-ink font-medium"
                          : "text-body hover:text-ink hover:bg-canvas-soft-2",
                      )}
                    >
                      {active && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-primary" />
                      )}
                      <Icon className="w-4 h-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer: version / user / theme / logout */}
        <div className="px-3 py-3 border-t border-hairline space-y-1">
          {version && (
            <Link
              href="/changelog"
              className="block text-xs text-mute hover:text-link px-2 py-1 rounded-md hover:bg-canvas-soft-2 font-mono"
              title="查看更新日志"
            >
              v{version}
            </Link>
          )}
          <div className="px-2 py-1 text-xs text-mute truncate">已登录:{user.username}</div>
          <div className="flex items-center justify-between">
            <ThemeToggle />
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 text-xs text-mute hover:text-error px-2 py-1 rounded-md hover:bg-canvas-soft-2"
            >
              <LogOut className="w-3.5 h-3.5" />
              退出
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        {title && (
          <header className="h-16 px-8 flex items-center bg-canvas border-b border-hairline sticky top-0 z-20">
            <h1 className="text-lg font-semibold text-ink tracking-tight tracking-display2">{title}</h1>
          </header>
        )}
        <div className="px-8 py-6">
          <div className="max-w-content mx-auto">{children}</div>
        </div>
      </main>
    </div>
  );
}
