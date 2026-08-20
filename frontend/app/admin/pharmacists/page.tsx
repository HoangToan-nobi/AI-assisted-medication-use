"use client";

import { useEffect, useState } from "react";
import { ApiError, approvePharmacist, listPendingPharmacists, rejectPharmacist, type PendingPharmacist } from "@/lib/api";

export default function AdminPharmacistsPage() {
  const [items, setItems] = useState<PendingPharmacist[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = () => listPendingPharmacists().then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được danh sách."));
  useEffect(() => { void load(); }, []);
  async function approve(id: string) { await approvePharmacist(id); await load(); }
  async function reject(id: string) { const reason = window.prompt("Lý do từ chối vai trò dược sĩ:"); if (!reason) return; await rejectPharmacist(id, reason); await load(); }
  return <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24 }}><h1>Hồ sơ dược sĩ chờ duyệt</h1>{error && <p className="error-text">{error}</p>}{items.length === 0 ? <p>Không có hồ sơ đang chờ.</p> : <div style={{ display: "grid", gap: 16 }}>{items.map((item) => <article className="auth-card" key={item.user_id}><h2>{item.ho_ten}</h2><p>{item.email}</p><p><b>Số CCHN:</b> {item.so_chung_chi_hanh_nghe}</p><p><b>Nơi công tác:</b> {item.noi_cong_tac}</p><div style={{ display: "flex", gap: 8 }}><button onClick={() => void approve(item.user_id)}>Duyệt dược sĩ</button><button onClick={() => void reject(item.user_id)}>Từ chối, chuyển thành người dùng</button></div></article>)}</div>}</main>;
}
