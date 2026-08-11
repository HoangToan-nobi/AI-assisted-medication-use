"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import BrandLogo from "@/components/BrandLogo";

type SidebarProps = { onCheck?: () => void; checking?: boolean };

export default function Sidebar({ onCheck, checking }: SidebarProps) {
  const pathname = usePathname();
  const isActive = (path: string) => pathname === path;
  const isMedicationActive = pathname === "/profile" || pathname.startsWith("/medications/");

  return (
    <nav className="bottom-nav sidebar" aria-label="Điều hướng chính">
      <div style={{ padding: "16px 16px 32px 0px" }}>
        <BrandLogo size="sm" />
      </div>
      <Link href="/dashboard" className={`bottom-nav__item ${isActive("/dashboard") ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="home" size={22} filled={isActive("/dashboard")} />
        <span>Trang chủ</span>
      </Link>
      <Link href="/profile" className={`bottom-nav__item ${isMedicationActive ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="medication" size={22} filled={isMedicationActive} />
        <span>Hồ sơ</span>
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
      <Link href="/emergency" className={`bottom-nav__item ${isActive("/emergency") ? "bottom-nav__item--active" : ""}`}>
        <MaterialIcon name="call" size={22} filled={isActive("/emergency")} />
        <span>Liên hệ</span>
      </Link>
    </nav>
  );
}
