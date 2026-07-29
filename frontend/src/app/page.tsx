import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-brand-50 to-brand-100 px-6">
      <div className="max-w-2xl text-center">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-brand-500 text-white text-4xl mb-6 shadow-lg">
          📊
        </div>
        <h1 className="text-4xl font-bold text-brand-700 mb-4">PPT 素材库</h1>
        <p className="text-lg text-gray-600 mb-8">
          面向 PPT 页级素材检索、理解、管理与复用的 BS 架构平台
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/login"
            className="px-6 py-3 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition shadow"
          >
            登录
          </Link>
          <Link
            href="/files"
            className="px-6 py-3 bg-white text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50 transition"
          >
            进入工作台
          </Link>
        </div>
      </div>
    </main>
  );
}
