"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminEmptyState, AdminPageHeader } from "@/components/AdminUI";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, listAdminDrugData, type AdminDrugItem } from "@/lib/api";

export default function AdminDrugsPage() {
  const [kind, setKind] = useState<"medication" | "product">("medication");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<AdminDrugItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { const result = await listAdminDrugData(query, kind); setItems(result.items); setTotal(result.total); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu thuốc."); }
    finally { setLoading(false); }
  }, [kind, query]);
  useEffect(() => { const timer = setTimeout(() => void load(), 250); return () => clearTimeout(timer); }, [load]);

  return (
    <main className="admin-page">
      <AdminPageHeader eyebrow="DỮ LIỆU Y KHOA" title="Quản lý dữ liệu thuốc" icon="medication" description="Kiểm tra danh mục hoạt chất, biệt dược và nguồn dữ liệu đang được hệ thống sử dụng." />
      <section className="panel admin-toolbar admin-toolbar--tabs">
        <div className="admin-segmented"><button className={kind === "medication" ? "active" : ""} onClick={() => setKind("medication")}><MaterialIcon name="pill" size={19} />Hoạt chất</button><button className={kind === "product" ? "active" : ""} onClick={() => setKind("product")}><MaterialIcon name="medication" size={19} />Biệt dược</button></div>
        <label className="admin-search"><MaterialIcon name="search" size={21} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={kind === "medication" ? "Tìm hoạt chất" : "Tìm tên biệt dược"} /></label>
      </section>
      <div className="admin-list-meta"><strong>{new Intl.NumberFormat("vi-VN").format(total)} bản ghi</strong><span>Hiển thị tối đa 100 kết quả</span></div>
      {error && <div className="admin-alert admin-alert--error"><MaterialIcon name="error" size={20} />{error}</div>}
      {loading ? <div className="admin-loading"><span className="spinner" />Đang tải dữ liệu...</div> : items.length === 0 ? <AdminEmptyState icon="search_off" title="Không có dữ liệu phù hợp" description="Thử một từ khóa khác trong danh mục đang chọn." /> : (
        <section className="admin-drug-grid">{items.map((item) => <article className="panel admin-drug-card" key={item.id}><span><MaterialIcon name={kind === "medication" ? "science" : "medication"} size={22} /></span><div><h2>{item.name}</h2><p>{item.detail || (kind === "medication" ? "Chưa có thông tin hoạt chất" : "Chưa phân loại")}</p><small><MaterialIcon name="database" size={15} />{item.source || "Nguồn nội bộ"}</small></div></article>)}</section>
      )}
      <div className="admin-info-note"><MaterialIcon name="info" size={19} /><p><strong>Chế độ an toàn:</strong> dữ liệu tương tác chỉ được cập nhật qua quy trình ETL có kiểm tra, không chỉnh sửa trực tiếp trên dashboard.</p></div>
    </main>
  );
}
