"use client";

import { useEffect, useState } from "react";
import { Plus, Tag as TagIcon } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Button from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";

interface Tag {
  id: string;
  name: string;
  category: string | null;
  source: string;
  status: string;
}

export default function TagsPage() {
  const toast = useToast();
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");

  async function load() {
    try {
      setTags(await api.get<Tag[]>(`/api/tags`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post(`/api/tags`, { name: name.trim(), category: category.trim() || null });
      toast.success("标签已创建");
      setName("");
      setCategory("");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "创建失败");
    }
  }

  async function toggleStatus(t: Tag) {
    const next = t.status === "active" ? "disabled" : "active";
    try {
      await api.patch(`/api/tags/${t.id}`, { status: next });
      toast.success(next === "active" ? "已启用" : "已停用");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  return (
    <AppShell title="标签管理">
      <div className="max-w-3xl space-y-6">
        {/* Create form */}
        <form onSubmit={create} className="bg-surface rounded-md shadow-e2 p-5">
          <div className="text-sm font-medium text-ink mb-3">新建标签</div>
          <div className="flex gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="标签名" className="flex-1" />
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="分类(如:主题/用途)"
              className="w-48"
            />
            <Button type="submit" variant="primary" leadingIcon={<Plus className="w-3.5 h-3.5" />}>
              新建
            </Button>
          </div>
        </form>

        {/* List */}
        {tags.length === 0 ? (
          <EmptyState icon={<TagIcon className="w-5 h-5" />} title="暂无标签" description="创建第一个标签来组织你的页面。" />
        ) : (
          <div className="bg-surface rounded-md shadow-e2 overflow-hidden">
            {tags.map((t) => {
              const active = t.status === "active";
              return (
                <div
                  key={t.id}
                  className="flex items-center justify-between px-4 py-3 border-b border-hairline last:border-0 hover:bg-canvas-soft-2 transition"
                >
                  <div className="flex items-center gap-3">
                    <Badge tone={active ? "info" : "default"}>{t.name}</Badge>
                    {t.category && <span className="text-xs text-mute">{t.category}</span>}
                    <span className="text-xs font-mono text-mute uppercase">{t.source}</span>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => toggleStatus(t)}>
                    {active ? "停用" : "启用"}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
