"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, LogIn } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { API_BASE as API_ROOT, fetchUiConfig } from "@/lib/version";
import type { UiConfig } from "@/lib/version";
import Button from "@/components/ui/Button";

export default function LoginPage() {
  const [ui, setUi] = useState<UiConfig | null>(null);

  useEffect(() => {
    fetchUiConfig().then(setUi);
    if (ui?.app_name) document.title = ui.app_name;
  }, [ui?.app_name]);

  function loginWithSSO() {
    // 顶层跳转到后端 /api/auth/login(后端 302 到 Authentik)
    window.location.href = `${API_BASE}/api/auth/login`;
  }

  return (
    <main className="relative min-h-screen flex items-center justify-center bg-canvas-soft overflow-hidden px-6">
      {ui?.mesh_enabled !== false && <div className="absolute inset-0 bg-mesh opacity-80" aria-hidden />}
      <div className="relative w-full max-w-md bg-canvas rounded-lg shadow-e5 p-8">
        <div className="text-center mb-8">
          {ui?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${API_ROOT}${ui.logo_url}`}
              alt={ui?.app_name || ""}
              className="w-12 h-12 rounded-md object-contain mx-auto mb-4"
            />
          ) : (
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-md bg-mesh border border-hairline mb-4" />
          )}
          <h1 className="text-2xl font-semibold text-ink tracking-tight tracking-display2">{ui?.app_name || "PPT 素材库"}</h1>
          <p className="text-sm text-body mt-1">请登录以继续</p>
        </div>
        <Button variant="primary" size="lg" block leadingIcon={<LogIn className="w-4 h-4" />} onClick={loginWithSSO}>
          使用 Authentik 登录
        </Button>
        <div className="mt-6 text-center">
          <a href="/" className="text-sm text-link hover:underline inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" /> 返回首页
          </a>
        </div>
      </div>
    </main>
  );
}
