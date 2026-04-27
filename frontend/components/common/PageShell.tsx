"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { clearAuthSession } from "@/lib/auth";
import { useReviewStore } from "@/stores/reviewStore";

const BRAND_LABEL = "合同审查工作台";
const NAV_UPLOAD = "上传合同文件";
const NAV_OVERVIEW = "结果总览看板";
const NAV_ISSUES = "逐条重点问题";
const USERNAME = "admin";
const EXTERNAL_LINKS = [
  {
    label: "国家市场监督管理总局 · 合同示范文本库",
    href: "https://htsfwb.samr.gov.cn/",
  },
  {
    label: "国家法律法规数据库",
    href: "https://flk.npc.gov.cn/",
  },
  {
    label: "腾讯元宝",
    href: "https://yuanbao.tencent.com/",
  },
  {
    label: "小理AI",
    href: "https://www.delilegal.com/ai",
  },
] as const;

function getTaskIdFromPath(pathname: string) {
  const match = pathname.match(/^\/review\/([^/]+)\/(overview|issues)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function PageShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const storedTaskId = useReviewStore((state) => state.taskId);
  const resetTaskData = useReviewStore((state) => state.resetTaskData);

  useEffect(() => {
    setIsUserMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!isUserMenuOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (menuRef.current?.contains(event.target as Node)) {
        return;
      }

      setIsUserMenuOpen(false);
    };

    window.addEventListener("pointerdown", handlePointerDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isUserMenuOpen]);

  const activeKey = pathname?.includes("/issues")
    ? "issues"
    : pathname?.includes("/overview")
      ? "overview"
      : "upload";

  const routeTaskId = pathname ? getTaskIdFromPath(pathname) : null;
  const taskId = routeTaskId ?? storedTaskId;

  const navItems = [
    { key: "upload", label: NAV_UPLOAD, href: "/review/new" },
    { key: "overview", label: NAV_OVERVIEW, href: taskId ? `/review/${taskId}/overview` : null },
    { key: "issues", label: NAV_ISSUES, href: taskId ? `/review/${taskId}/issues` : null },
  ] as const;

  const handleLogout = () => {
    clearAuthSession();
    resetTaskData();
    window.location.assign("/login");
  };

  return (
    <div className="page-shell">
      <div className="workbench-layout">
        <aside className="workbench-sidebar">
          <div className="workbench-brand">{BRAND_LABEL}</div>

          <nav className="workbench-nav">
            {navItems.map((item) => {
              const className = `workbench-nav-link ${activeKey === item.key ? "workbench-nav-link-active" : ""}`;

              if (!item.href) {
                return (
                  <span key={item.key} className={`${className} workbench-nav-link-disabled`}>
                    {item.label}
                  </span>
                );
              }

              return (
                <Link key={item.key} href={item.href} className={className}>
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="sidebar-links">
            <div className="sidebar-links-title">常用入口</div>
            <div className="sidebar-links-list">
              {EXTERNAL_LINKS.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                  className="sidebar-link-item"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>
        </aside>

        <main className="workbench-main">
          <div className="workbench-topbar">
            <div ref={menuRef} className="user-menu">
              <button
                type="button"
                className="user-menu-trigger"
                onClick={() => setIsUserMenuOpen((value) => !value)}
                aria-haspopup="menu"
                aria-expanded={isUserMenuOpen}
              >
                <span className="user-avatar" aria-hidden="true">
                  {USERNAME.slice(0, 1).toUpperCase()}
                </span>
              </button>

              {isUserMenuOpen ? (
                <div className="user-menu-popover" role="menu">
                  <div className="user-menu-name">{USERNAME}</div>
                  <button type="button" className="user-menu-action" onClick={handleLogout} role="menuitem">
                    退出登录
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          <div className="workbench-inner">{children}</div>
        </main>
      </div>
    </div>
  );
}
