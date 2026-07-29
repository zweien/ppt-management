"use client";

import { useEffect, useState } from "react";
import { Trash2, RotateCcw } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Table, THead, TH, TBody, TR, TD } from "@/components/ui/DataTable";
import { useToast } from "@/components/ui/Toast";

interface Presentation {
  id: string;
  title: string;
  page_count: number;
  created_at: string;
  deleted_at: string;
}

export default function TrashPage() {
  const toast = useToast();
  const [items, setItems] = useState<Presentation[]>([]);

  async function load() {
    try {
      setItems(await api.get<Presentation[]>(`/api/presentations?include_deleted=true`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function restore(id: string) {
    try {
      await api.post(`/api/presentations/${id}/restore`);
      toast.success("已恢复");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "恢复失败");
    }
  }

  const deleted = items.filter((p) => p.deleted_at);

  return (
    <AppShell title="回收站">
      <div className="space-y-4">
        <p className="text-xs text-mute">软删除的文件在此可恢复。索引立即不可见,对象延迟清理。</p>
        {deleted.length === 0 ? (
          <EmptyState icon={<Trash2 className="w-5 h-5" />} title="回收站为空" description="删除的文件会暂存在这里,可以随时恢复。" />
        ) : (
          <Table>
            <THead>
              <TH>文件名</TH>
              <TH>页数</TH>
              <TH>删除时间</TH>
              <TH className="text-right">操作</TH>
            </THead>
            <TBody>
              {deleted.map((p) => (
                <TR key={p.id}>
                  <TD className="text-mute">{p.title}</TD>
                  <TD className="text-mute">{p.page_count}</TD>
                  <TD className="text-mute text-xs">{new Date(p.deleted_at).toLocaleString("zh-CN")}</TD>
                  <TD className="text-right">
                    <Button size="sm" variant="secondary" leadingIcon={<RotateCcw className="w-3.5 h-3.5" />} onClick={() => restore(p.id)}>
                      恢复
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>
    </AppShell>
  );
}
