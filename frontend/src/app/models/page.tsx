import { redirect } from "next/navigation";

// 模型配置已并入「设置」页(/settings)的「模型配置」Tab。这里重定向保持兼容。
export default function ModelsPage() {
  redirect("/settings");
}
