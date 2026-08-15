"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import BrandLogo from "@/components/BrandLogo";

type SidebarProps = { onCheck?: () => void; checking?: boolean; collapsed?: boolean; onToggleCollapsed?: () => void };

function SidebarContent({ onCheck, checking, collapsed = false, onToggleCollapsed }: SidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isActive = (path: string) => pathname === path;
  const isPrescriptionsTab = searchParams.get("tab") === "prescriptions";
  const isPersonalInfoActive = pathname === "/profile" && !isPrescriptionsTab;
  const isPrescriptionsActive = (pathname === "/profile" && isPrescriptionsTab) || pathname.startsWith("/medications/");

  return (
    <nav className={`bottom-nav sidebar ${collapsed ? "sidebar--collapsed" : ""}`} aria-label="Điều hướng chính">
      <div className="sidebar__brand-row">
        <Link href="/dashboard" className="sidebar__brand-link" aria-label="Về trang chủ MediCheck">
          <BrandLogo size="sm" className="sidebar__brand" />
        </Link>
        {onToggleCollapsed && <button type="button" className="sidebar__toggle" onClick={onToggleCollapsed} aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} title={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}><MaterialIcon name={collapsed ? "keyboard_double_arrow_right" : "keyboard_double_arrow_left"} size={22} /></button>}
      </div>
      <Link href="/dashboard" className={`bottom-nav__item ${isActive("/dashboard") ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="home" size={22} filled={isActive("/dashboard")} />
        <span>Trang chủ</span>
      </Link>
      <Link href="/profile" className={`bottom-nav__item ${isPersonalInfoActive ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="person" size={22} filled={isPersonalInfoActive} />
        <span>Thông tin cá nhân</span>
      </Link>
      <Link href="/profile?tab=prescriptions" className={`bottom-nav__item ${isPrescriptionsActive ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="medication" size={22} filled={isPrescriptionsActive} />
        <span>Đơn thuốc của tôi</span>
      </Link>
      {onCheck ? (
        <button type="button" className="bottom-nav__item" onClick={onCheck} disabled={checking}>
          {checking ? <span className="spinner spinner--sm" aria-hidden="true" /> : <MaterialIcon name="analytics" size={22} />}
          <span>{checking ? "Đang kiểm tra" : "Tương tác"}</span>
        </button>
      ) : (
        <Link href="/interaction" className={`bottom-nav__item ${isActive("/interaction") ? "bottom-nav__item--active" : ""}`}>
          <MaterialIcon name="analytics" size={22} filled={isActive("/interaction")} />
          <span>Tương tác</span>
        </Link>
      )}
      <Link href="/history" className={`bottom-nav__item ${isActive("/history") ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="history" size={22} filled={isActive("/history")} />
        <span>Lịch sử</span>
      </Link>
    </nav>
  );
}

// useSearchParams() cần 1 Suspense boundary bao ngoài (Next.js yêu cầu) - Sidebar
// sống trong layout dùng chung nhiều trang, không tự bọc Suspense ở nơi gọi được.
export default function Sidebar(props: SidebarProps) {
  return (
    <Suspense fallback={null}>
      <SidebarContent {...props} />
    </Suspense>
  );
}
