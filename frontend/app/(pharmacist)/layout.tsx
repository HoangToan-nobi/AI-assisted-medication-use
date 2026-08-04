"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getInitials } from "@/lib/format";
import { clearSession, getSession, type Session } from "@/lib/auth";

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
    <>
      <nav className="nav">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true">
            🛡️
          </span>
          MedGuard AI
        </span>
        <div className="nav-links">
          <Link href="/patients" className={`nav-link ${pathname === "/patients" ? "active" : ""}`}>
            Bệnh nhân phụ trách
          </Link>
        </div>
        <span className="spacer" />
        <div className="nav-user">
          <span className="avatar">{getInitials(session.hoTen)}</span>
          <span className="nav-user-name">{session.hoTen}</span>
          <button className="ghost" onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
      </nav>
      {children}
    </>
  );
}
