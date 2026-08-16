"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import BrandLogo from "@/components/BrandLogo";
import MaterialIcon from "@/components/MaterialIcon";
import NotificationBell from "@/components/NotificationBell";
import { clearSession, getSession, onSessionUpdated, type Session } from "@/lib/auth";
import Link from "next/link";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [checked, setChecked] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const current = getSession();
    if ((!current || current.vaiTro !== "patient") && pathname !== "/interaction") {
      router.replace("/");
      return;
    }
    setSession(current);
    setChecked(true);
  }, [router]);

  useEffect(() => onSessionUpdated(() => setSession(getSession())), []);

  if (!checked) return null;

  if (!session && pathname === "/interaction") {
    return <div className="app-shell"><header className="patient-header"><BrandLogo size="sm" /><Link className="guest-login-link" href="/">Đăng nhập để lưu lịch sử</Link></header><div className="app-content">{children}</div></div>;
  }
  if (!session) return null;

  function logout() {
    clearSession();
    router.replace("/");
  }

  return (
    <div className={`app-shell app-shell--with-nav ${sidebarCollapsed ? "app-shell--sidebar-collapsed" : ""}`}>
      <header className="patient-header">
        <div className="patient-header__actions" style={{ marginLeft: "auto" }}>
          <NotificationBell patientId={session.userId} token={session.accessToken} />
          <Link className="patient-header__name" href="/profile" title="Hồ sơ của tôi">{session.hoTen}</Link>
          <button className="icon-btn" onClick={logout} aria-label="Đăng xuất" title="Đăng xuất">
            <MaterialIcon name="logout" size={20} />
          </button>
        </div>
      </header>
      <div className="app-content">{children}</div>
      <Sidebar collapsed={sidebarCollapsed} onToggleCollapsed={() => setSidebarCollapsed((current) => !current)} />
      <span className="sr-only">Đang ở trang {pathname}</span>
    </div>
  );
}
