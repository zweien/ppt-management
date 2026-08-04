"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import Button from "@/components/ui/Button";
import { API_BASE, fetchUiConfig } from "@/lib/version";
import type { UiConfig } from "@/lib/version";

export default function Home() {
  const [ui, setUi] = useState<UiConfig | null>(null);

  useEffect(() => {
    fetchUiConfig().then(setUi);
    if (ui?.app_name) document.title = ui.app_name;
  }, [ui?.app_name]);

  return (
    <main className="relative min-h-screen flex flex-col items-center justify-center bg-canvas-soft overflow-hidden px-6">
      {ui?.mesh_enabled !== false && <div className="absolute inset-0 bg-mesh opacity-90" aria-hidden />}
      <div className="relative max-w-2xl text-center">
        {ui?.logo_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`${API_BASE}${ui.logo_url}`}
            alt={ui?.app_name || ""}
            className="w-14 h-14 rounded-md object-contain mx-auto mb-6"
          />
        )}
        <span className="inline-block text-[14px] font-mono uppercase tracking-wider text-body bg-canvas/80 backdrop-blur border border-hairline rounded-pill px-3 py-1 mb-6">
          {ui?.app_name || "PPT 素材库"}
        </span>
        <h1 className="text-[44px] leading-[1.05] font-semibold tracking-tight tracking-display1 text-ink mb-4">
          检索、理解、管理与复用每一页幻灯片。
        </h1>
        <p className="text-lg text-body mb-8 leading-relaxed">
          面向 PPT 页级素材检索、理解、管理与复用的 BS 架构平台。
        </p>
        <div className="flex gap-3 justify-center">
          <Link href="/login">
            <Button variant="primary" size="lg" leadingIcon={<ArrowRight className="w-4 h-4" />}>
              开始使用
            </Button>
          </Link>
          <Link href="/files">
            <Button variant="secondary" size="lg">
              进入工作台
            </Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
