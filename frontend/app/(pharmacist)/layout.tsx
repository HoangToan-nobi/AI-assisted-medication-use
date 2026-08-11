"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getInitials } from "@/lib/format";
import { clearSession, getSession, type Session } from "@/lib/auth";
import BrandLogo from "@/components/BrandLogo";
import MaterialIcon from "@/components/MaterialIcon";

export default function PharmacistLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (!s || s.vaiTro !== "pharmacist") {
      router.replace("/");
      return;
    }
    setSession(s);
    setChecked(true);
  }, [router]);

  function handleLogout() {
    clearSession();
    router.replace("/");
  }

  if (!checked || !session) return null;

  return (
    <div className="app-shell app-shell--with-nav">
      <header className="patient-header">
        <div className="patient-header__actions" style={{ marginLeft: "auto" }}>
          <span className="patient-header__name" title="Hồ sơ dược sĩ">{session.hoTen}</span>
          <button className="icon-btn" onClick={handleLogout} aria-label="Đăng xuất" title="Đăng xuất">
            <MaterialIcon name="logout" size={20} />
          </button>
        </div>
      </header>
      <div className="app-content">{children}</div>
      <nav className="bottom-nav sidebar" aria-label="Điều hướng chính">
        <div style={{ padding: "16px 16px 32px 0px" }}>
          <BrandLogo size="sm" />
        </div>
        <Link href="/pharmacist-dashboard" className={`bottom-nav__item ${pathname === "/pharmacist-dashboard" ? "bottom-nav__item--active" : ""}`}>
          <MaterialIcon name="home" size={22} filled={pathname === "/pharmacist-dashboard"} />
          <span>Trang chủ</span>
        </Link>
        <Link href="/pharmacist-lookup" className={`bottom-nav__item ${pathname === "/pharmacist-lookup" ? "bottom-nav__item--active" : ""}`}>
          <MaterialIcon name="analytics" size={22} filled={pathname === "/pharmacist-lookup"} />
          <span>Tra cứu tương tác</span>
        </Link>
      </nav>
      <span className="sr-only">Đang ở trang {pathname}</span>
    </div>
  );
}
