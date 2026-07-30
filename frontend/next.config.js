/** @type {import('next').NextConfig} */
// API_BACKEND:服务端 rewrites 代理目标。
// 构建时注入(Dockerfile.web 的 ARG API_BACKEND)→ 容器内用 docker 服务名 api:8000。
// 运行时前后端同源(都走 web:3000),/api/* 由 Next 代理到后端 → session cookie 同域。
// (next.config.js 在构建时求值,故用 ARG 而非运行时 env。)
const API_BACKEND = process.env.API_BACKEND || "http://localhost:18000";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_BACKEND}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
