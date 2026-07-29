"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { CHANGELOG, fetchVersion } from "@/lib/version";
import { Badge } from "@/components/ui/Badge";
import type { BadgeTone } from "@/lib/status";

// Section-kind → semantic tone (Vercel palette).
const KIND_TONE: Record<string, BadgeTone> = {
  "🎉 里程碑": "primary",
  "✨ 新功能": "success",
  "🐛 修复": "warning",
  "📚 文档": "info",
  "♻️ 重构": "violet",
  "⚡ 性能": "info",
};

export default function ChangelogPage() {
  const [version, setVersion] = useState("");

  useEffect(() => {
    fetchVersion().then(setVersion);
  }, []);

  return (
    <AppShell title="更新日志">
      <div className="max-w-3xl space-y-6">
        {/* Current version card */}
        <div className="bg-surface rounded-md shadow-e2 p-5 flex items-center justify-between">
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-mute mb-1">当前版本</div>
            <div className="text-2xl font-semibold text-ink tracking-tight tracking-display2 font-mono">
              {version ? `v${version}` : "加载中..."}
            </div>
          </div>
          <div className="text-right text-xs text-mute space-y-0.5">
            <div>遵循 SemVer 语义化版本</div>
            <div>
              发版流程见 <code className="font-mono">docs/agents/versioning.md</code>
            </div>
          </div>
        </div>

        {/* Version entries */}
        {CHANGELOG.map((entry) => {
          const isUnreleased = entry.version === "Unreleased";
          const isEmpty = entry.sections.every((s) => s.items.length === 0);
          return (
            <div
              key={entry.version}
              className={`bg-surface rounded-md shadow-e2 p-5 ${isUnreleased ? "border border-dashed border-hairline-strong" : ""}`}
            >
              <div className="flex items-center gap-3 mb-4 pb-3 border-b border-hairline">
                <span className={`text-base font-semibold font-mono ${isUnreleased ? "text-mute" : "text-ink"}`}>
                  {isUnreleased ? "Unreleased" : `v${entry.version}`}
                </span>
                {entry.date && <span className="text-xs text-mute">{entry.date}</span>}
                {isUnreleased && <Badge tone="default">开发中</Badge>}
              </div>

              {isEmpty ? (
                <div className="text-sm text-mute">暂无变更记录</div>
              ) : (
                <div className="space-y-4">
                  {entry.sections.map((section) => (
                    <div key={section.kind}>
                      <div className="mb-2">
                        <Badge tone={KIND_TONE[section.kind] || "default"}>{section.kind}</Badge>
                      </div>
                      <ul className="space-y-1.5 ml-1">
                        {section.items.map((item, i) => (
                          <li key={i} className="text-sm text-body flex gap-2 leading-relaxed">
                            <span className="text-mute mt-1 shrink-0">•</span>
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AppShell>
  );
}
