"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, logout } from "@/lib/api";
import { clearSession, saveSession, sessionFromAuth } from "@/lib/auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => { getMe().then((auth) => { if (auth.vai_tro !== "admin") throw new Error(); saveSession(sessionFromAuth(auth)); setReady(true); }).catch(() => router.replace("/auth")); }, [router]);
  if (!ready) return null;
  return <div className="app-content"><header style={{ display: "flex", justifyContent: "space-between", padding: 20 }}><strong>Quản trị MediCheck</strong><button onClick={() => void logout().finally(() => { clearSession(); router.replace("/auth"); })}>Đăng xuất</button></header>{children}</div>;
}
