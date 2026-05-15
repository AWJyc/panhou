/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    // 部署时不让 lint 警告阻断 build；CI / 本地开发还能跑 npm run lint
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
    ];
  },
};

export default nextConfig;
