import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";
import { AuthProvider } from "@/components/AuthContext";

export const metadata: Metadata = {
  title: "盘后 · POST-CLOSE",
  description: "每日全球股市盘后报告：A 股 · 美股 · 日股 · 韩股",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="font-sans bg-page text-ink">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
