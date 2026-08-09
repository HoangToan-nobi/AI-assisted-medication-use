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
    <div className="pharmacist-shell">
      <aside className="pharmacist-nav pharmacist-sidebar">
        <BrandLogo size="sm" />
        <Link href="/patients" className={`pharmacist-nav__link ${pathname === "/patients" ? "active" : ""}`}>
          <MaterialIcon name="group" size={20} />
          Bệnh nhân phụ trách
        </Link>
        <span className="spacer" />
        <div className="pharmacist-nav__user">
          <span className="avatar">{getInitials(session.hoTen)}</span>
          <span className="pharmacist-nav__user-name">{session.hoTen}</span>
          <button className="icon-btn" onClick={handleLogout} aria-label="Đăng xuất" title="Đăng xuất">
            <MaterialIcon name="logout" size={20} />
          </button>
        </div>
      </aside>
      <div className="pharmacist-content">{children}</div>
    </div>
  );
}
