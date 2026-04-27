import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "\u5408\u540c\u5ba1\u67e5\u5de5\u4f5c\u53f0",
  description: "\u9762\u5411 self-use \u573a\u666f\u7684\u5408\u540c\u5ba1\u67e5\u524d\u7aef\u5de5\u4f5c\u53f0",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
