"use client";

import { useEffect, useState } from "react";
import { Save, AlertTriangle } from "lucide-react";
import AppShell from "@/components/AppShell";
import ModelConfigSection from "@/components/ModelConfigSection";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";

interface FieldDef {
  key: string;
  label: string;
  type: "int" | "str" | "list_str";
  value: number | string | string[];
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

type TabKey = "upload" | "ai" | "access" | "models" | "system";

const TAB_TO_GROUP: Record<string, string> = {
  upload: "upload",
  ai: "ai",
  access: "access",
};

export default function SettingsPage() {
  const toast = useToast();
  const [data, setData] = useState<SettingsData | null>(null);
  const [tab, setTab] = useState<TabKey>("upload");
  // 本地草稿:key -> 编辑中的值。保存时提交。
  const [draft, setDraft] = useState<Record<string, number | string | string[]>>({});
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

  function editValue(key: string, v: number | string | string[]) {
    setDraft((prev) => ({ ...prev, [key]: v }));
  }

  function currentValue(f: FieldDef): number | string | string[] {
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
            { key: "upload", label: "上传与安全" },
            { key: "ai", label: "AI 服务" },
            { key: "access", label: "访问与安全" },
            { key: "models", label: "模型配置" },
            { key: "system", label: "系统信息" },
          ]}
        />

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
  value: number | string | string[];
  onChange: (v: number | string | string[]) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <label className="text-[13px] font-medium text-body">{field.label}</label>
        {field.restart_required && (
          <span className="inline-flex items-center gap-1 text-xs text-warning-deep">
            <AlertTriangle className="w-3 h-3" /> 需重启生效
          </span>
        )}
        <span className="text-[11px] font-mono text-mute ml-auto">{field.key}</span>
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
    </div>
  );
}
