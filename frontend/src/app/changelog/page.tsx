"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { CHANGELOG } from "@/lib/version";
import { fetchVersion } from "@/lib/version";

// 各分类的配色
const KIND_STYLES: Record<string, string> = {
  "🎉 里程碑": "bg-brand-50 text-brand-700",
  "✨ 新功能": "bg-green-50 text-green-700",
  "🐛 修复": "bg-orange-50 text-orange-700",
  "📚 文档": "bg-blue-50 text-blue-700",
  "♻️ 重构": "bg-purple-50 text-purple-700",
  "⚡ 性能": "bg-yellow-50 text-yellow-700",
};

export default function ChangelogPage() {
  const [version, setVersion] = useState("");

  useEffect(() => {
    fetchVersion().then(setVersion);
  }, []);

  return (
    <AppShell title="更新日志">
      <div className="max-w-3xl space-y-6">
        {/* 当前版本卡片 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400">当前版本</div>
            <div className="text-2xl font-semibold text-brand-700">
              {version ? `v${version}` : "加载中..."}
            </div>
          </div>
          <div className="text-right text-xs text-gray-400">
            <div>遵循 SemVer 语义化版本</div>
            <div>发版流程见 <code>docs/agents/versioning.md</code></div>
          </div>
        </div>

        {/* 版本列表 */}
        {CHANGELOG.map((entry) => {
          const isUnreleased = entry.version === "Unreleased";
          const isEmpty = entry.sections.every((s) => s.items.length === 0);
          return (
            <div
              key={entry.version}
              className={`bg-white rounded-xl border p-5 ${
                isUnreleased ? "border-dashed border-gray-300" : "border-gray-200"
              }`}
            >
              <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-100">
                <span className={`text-lg font-semibold ${isUnreleased ? "text-gray-400" : "text-gray-800"}`}>
                  {isUnreleased ? "Unreleased" : `v${entry.version}`}
                </span>
                {entry.date && <span className="text-xs text-gray-400">{entry.date}</span>}
                {isUnreleased && (
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded">开发中</span>
                )}
              </div>

              {isEmpty ? (
                <div className="text-sm text-gray-300">暂无变更记录</div>
              ) : (
                <div className="space-y-4">
                  {entry.sections.map((section) => (
                    <div key={section.kind}>
                      <div className={`inline-block text-xs px-2 py-0.5 rounded mb-2 ${KIND_STYLES[section.kind] || "bg-gray-50 text-gray-600"}`}>
                        {section.kind}
                      </div>
                      <ul className="space-y-1.5 ml-1">
                        {section.items.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 flex gap-2">
                            <span className="text-gray-300 mt-0.5">•</span>
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
