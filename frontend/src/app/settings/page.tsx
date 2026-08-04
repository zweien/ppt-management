"use client";

import { useEffect, useRef, useState } from "react";
import { Save, AlertTriangle, UploadCloud, Trash2 } from "lucide-react";
import AppShell from "@/components/AppShell";
import ModelConfigSection from "@/components/ModelConfigSection";
import { api, ApiError, API_BASE } from "@/lib/api";
import { refreshRoot } from "@/lib/version";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { Checkbox } from "@/components/ui/Checkbox";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";

interface FieldDef {
  key: string;
  label: string;
  type: "int" | "str" | "list_str" | "bool" | "select_str";
  value: number | string | string[] | boolean;
  options?: string[] | null;
  restart_required?: boolean;
}
interface GroupDef {
  key: string;
  label: string;
  fields: FieldDef[];
}
interface SettingsData {
  groups: GroupDef[];
  system_info: Record<string, Record<string, string>>;
}

type TabKey = "ui" | "upload" | "ai" | "access" | "models" | "system";

const TAB_TO_GROUP: Record<string, string> = {
  ui: "ui",
  upload: "upload",
  ai: "ai",
  access: "access",
};

export default function SettingsPage() {
  const toast = useToast();
  const [data, setData] = useState<SettingsData | null>(null);
  const [tab, setTab] = useState<TabKey>("ui");
  // 本地草稿:key -> 编辑中的值。保存时提交。
  const [draft, setDraft] = useState<Record<string, number | string | string[] | boolean>>({});
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const d = await api.get<SettingsData>(`/api/settings`);
      setData(d);
      setDraft({});
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        toast.error("需要管理员权限");
      } else {
        toast.error(e instanceof ApiError ? e.message : "加载失败");
      }
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** UI 配置(logo / 名称等)改动后,刷新 GET / 缓存让全站生效。 */
  async function handleUiChanged() {
    await refreshRoot();
  }

  function editValue(key: string, v: number | string | string[] | boolean) {
    setDraft((prev) => ({ ...prev, [key]: v }));
  }

  function currentValue(f: FieldDef): number | string | string[] | boolean {
    return f.key in draft ? draft[f.key] : f.value;
  }

  async function save() {
    if (Object.keys(draft).length === 0) {
      toast.info("没有改动");
      return;
    }
    setSaving(true);
    try {
      await api.patch(`/api/settings`, draft);
      toast.success(`已保存 ${Object.keys(draft).length} 项`);
      // UI 配置(app_name/mesh/theme)改动需刷新 GET / 缓存以全站生效。
      if (Object.keys(draft).some((k) => ["APP_DISPLAY_NAME", "MESH_ENABLED", "DEFAULT_THEME"].includes(k))) {
        await refreshRoot();
      }
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const currentGroup = data?.groups.find((g) => g.key === TAB_TO_GROUP[tab]);
  const dirty = Object.keys(draft).length > 0;

  return (
    <AppShell title="设置">
      <div className="space-y-5">
        <Tabs<TabKey>
          value={tab}
          onChange={setTab}
          items={[
            { key: "ui", label: "界面" },
            { key: "upload", label: "上传与安全" },
            { key: "ai", label: "AI 服务" },
            { key: "access", label: "访问与安全" },
            { key: "models", label: "模型配置" },
            { key: "system", label: "系统信息" },
          ]}
        />

        {/* UI Tab 的 logo 上传区(在可调项之上) */}
        {tab === "ui" && <LogoSection onChanged={handleUiChanged} />}

        {/* 可调配置区(upload / ai / access 共用渲染) */}
        {currentGroup && (
          <div className="bg-surface rounded-md shadow-e2 p-6 max-w-2xl space-y-5">
            <h2 className="text-sm font-medium text-ink">{currentGroup.label}</h2>
            {currentGroup.fields.map((f) => (
              <FieldRow key={f.key} field={f} value={currentValue(f)} onChange={(v) => editValue(f.key, v)} />
            ))}
            <div className="flex items-center gap-3 pt-2 border-t border-hairline">
              <Button variant="primary" leadingIcon={<Save className="w-3.5 h-3.5" />} onClick={save} loading={saving} disabled={!dirty}>
                保存改动{dirty ? `(${Object.keys(draft).length})` : ""}
              </Button>
              {dirty && (
                <Button variant="ghost" onClick={() => setDraft({})}>
                  放弃
                </Button>
              )}
              <span className="text-xs text-mute ml-auto">改动后立即生效(api/worker 缓存 ≤30s)</span>
            </div>
          </div>
        )}

        {/* 模型配置 Tab */}
        {tab === "models" && <ModelConfigSection />}

        {/* 系统信息 Tab(只读脱敏) */}
        {tab === "system" && data && (
          <div className="space-y-4 max-w-2xl">
            <p className="text-xs text-mute">当前运行环境配置(来自环境变量,只读脱敏)。这些项需通过环境变量修改后重启生效。</p>
            {Object.entries(data.system_info).map(([section, kvs]) => (
              <div key={section} className="bg-surface rounded-md shadow-e2 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-hairline bg-canvas-soft">
                  <span className="text-sm font-medium text-ink">{section}</span>
                </div>
                <dl className="divide-y divide-hairline">
                  {Object.entries(kvs).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between px-4 py-2.5">
                      <dt className="text-xs font-mono text-mute">{k}</dt>
                      <dd className="text-sm text-ink font-mono ml-4 truncate max-w-[60%]" title={String(v)}>
                        {String(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function FieldRow({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: number | string | string[] | boolean;
  onChange: (v: number | string | string[] | boolean) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <label className="text-[15px] font-medium text-body">{field.label}</label>
        {field.restart_required && (
          <span className="inline-flex items-center gap-1 text-xs text-warning-deep">
            <AlertTriangle className="w-3 h-3" /> 需重启生效
          </span>
        )}
        <span className="text-[13px] font-mono text-mute ml-auto">{field.key}</span>
      </div>
      {field.type === "int" && (
        <Input
          type="number"
          inputSize="md"
          value={String(value)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      )}
      {field.type === "str" && (
        <Input inputSize="md" value={String(value)} onChange={(e) => onChange(e.target.value)} />
      )}
      {field.type === "list_str" && (
        <Input
          inputSize="md"
          value={Array.isArray(value) ? value.join(", ") : String(value)}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          placeholder="逗号分隔,如 .pptx, .ppt"
        />
      )}
      {field.type === "bool" && (
        <Checkbox checked={!!value} onChange={(e) => onChange(e.target.checked)} label={value ? "已启用" : "已关闭"} />
      )}
      {field.type === "select_str" && (
        <Select inputSize="md" value={String(value)} onChange={(e) => onChange(e.target.value)}>
          {(field.options || []).map((o) => (
            <option key={o} value={o}>
              {o === "light" ? "浅色" : o === "dark" ? "深色" : o}
            </option>
          ))}
        </Select>
      )}
    </div>
  );
}

/** Logo 上传 + 移除区。 */
function LogoSection({ onChanged }: { onChanged: () => Promise<void> | void }) {
  const toast = useToast();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refreshLogo() {
    // 拉最新 ui_config 看 logo_url 是否存在(避免浏览器缓存用时间戳)
    const r = await fetch(`${API_BASE}/`).then((x) => x.json());
    setLogoUrl(r.ui_config?.logo_url || null);
  }
  useEffect(() => {
    refreshLogo();
  }, []);

  async function upload(file: File) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.postForm(`/api/settings/logo`, form);
      toast.success("logo 已更新");
      await refreshLogo();
      await onChanged();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.delete(`/api/settings/logo`);
      toast.success("logo 已移除");
      await refreshLogo();
      await onChanged();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "移除失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-surface rounded-md shadow-e2 p-6 max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-ink">品牌 Logo</h2>
        <span className="text-xs text-mute">显示在侧边栏 / 登录页 / 首页;未设置时用 mesh 渐变方块</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-md border border-hairline bg-canvas-soft-2 flex items-center justify-center overflow-hidden shrink-0">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`${API_BASE}${logoUrl}?t=${Date.now()}`} alt="logo" className="w-full h-full object-contain" />
          ) : (
            <span className="w-10 h-10 rounded-sm bg-mesh" />
          )}
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              if (e.target) e.target.value = "";
            }}
          />
          <Button
            variant="primary"
            size="md"
            leadingIcon={<UploadCloud className="w-3.5 h-3.5" />}
            loading={busy}
            onClick={() => fileRef.current?.click()}
          >
            上传 logo
          </Button>
          {logoUrl && (
            <Button variant="ghost" size="md" leadingIcon={<Trash2 className="w-3.5 h-3.5" />} disabled={busy} onClick={remove}>
              移除
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs text-mute">支持 PNG / JPG / WEBP / SVG / GIF,≤ 2MB。</p>
    </div>
  );
}
