"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, getSession, type Session } from "@/lib/auth";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (!s || s.vaiTro !== "patient") {
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
        <Link href="/dashboard">Trang chủ</Link>
        <Link href="/medications">Thêm thuốc</Link>
        <span className="spacer" />
        <span>{session.hoTen}</span>
        <button className="secondary" onClick={handleLogout}>
          Đăng xuất
        </button>
      </nav>
      {children}
    </>
  );
}
