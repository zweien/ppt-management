"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { API_BASE as API_ROOT, fetchUiConfig } from "@/lib/version";
import type { UiConfig } from "@/lib/version";
import Button from "@/components/ui/Button";
import { Input, Field } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ui, setUi] = useState<UiConfig | null>(null);

  useEffect(() => {
    fetchUiConfig().then(setUi);
    if (ui?.app_name) document.title = ui.app_name;
  }, [ui?.app_name]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "登录失败");
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      router.push("/files");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
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
        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="用户名" htmlFor="username">
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              inputSize="lg"
              required
            />
          </Field>
          <Field label="密码" htmlFor="password">
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              inputSize="lg"
              required
            />
          </Field>
          {error && (
            <div className="text-sm text-error-deep bg-error-soft border border-error/20 rounded-sm px-3 py-2">
              {error}
            </div>
          )}
          <Button type="submit" variant="primary" size="lg" block loading={loading}>
            {loading ? "登录中..." : "登录"}
          </Button>
        </form>
        <div className="mt-6 text-center">
          <Link
            href="/"
            className="text-sm text-link hover:underline inline-flex items-center gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> 返回首页
          </Link>
        </div>
      </div>
    </main>
  );
}
