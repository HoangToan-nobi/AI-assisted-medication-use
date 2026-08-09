"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, getInteractionCheckDetail, listPatientChecksForPharmacist, submitPharmacistReview, type AgentCheckResult, type InteractionCheckSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";

function ReviewContent() {
  const router = useRouter();
  const patientId = useSearchParams().get("patientId");
  const session = getSession();
  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentCheckResult | null>(null);
  const [ghiChu, setGhiChu] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!session || !patientId) return;
    listPatientChecksForPharmacist(patientId, session.accessToken).then((list) => { setChecks(list); if (list.length) setSelectedCheckId(list[0].id); }).catch((err) => setError(err instanceof ApiError ? err.message : "Kh�ng t?i du?c danh s�ch l?n ki?m tra")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);
  useEffect(() => {
    if (!session || !selectedCheckId) return;
    setSubmitted(false); setGhiChu("");
    getInteractionCheckDetail(selectedCheckId, session.accessToken).then(setDetail).catch((err) => setError(err instanceof ApiError ? err.message : "Kh�ng t?i du?c chi ti?t"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCheckId]);
  async function handleConfirm() {
    if (!session || !selectedCheckId) return;
    setSubmitting(true); setError(null);
    try { await submitPharmacistReview(selectedCheckId, ghiChu, session.accessToken); setSubmitted(true); setChecks((prev) => prev.map((c) => c.id === selectedCheckId ? { ...c, trang_thai_xac_nhan: "da_xac_nhan" } : c)); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Kh�ng x�c nh?n du?c"); }
    finally { setSubmitting(false); }
  }
  if (!session) return null;
  if (!patientId) return <main><div className="empty-state"><MaterialIcon name="person_search" size={40} /><strong>Chua ch?n b?nh nh�n</strong><span>Vui l�ng ch?n b?nh nh�n t? danh s�ch ph? tr�ch.</span><button onClick={() => router.push("/patients")}>V? danh s�ch b?nh nh�n</button></div></main>;

  return <main>
    <div className="page-header page-header--in-content"><button className="page-header__back" onClick={() => router.push("/patients")} aria-label="Quay l?i"><MaterialIcon name="arrow_back" size={22} /></button><div><p className="eyebrow">XEM X�T CHUY�N M�N</p><h1 className="page-header__title">Chi ti?t c?nh b�o</h1></div></div>
    <section className="review-toolbar"><div><p className="eyebrow">L?CH S? KI?M TRA</p><h2>Ch?n l?n ki?m tra c?n xem</h2></div>{checks.length > 0 && <span className="badge badge-confirmed">{checks.length} l?n ki?m tra</span>}</section>
    {loading && <div className="loading-row"><span className="spinner" /> Dang t?i...</div>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {!loading && checks.length === 0 && <div className="empty-state"><MaterialIcon name="history" size={40} /><strong>Chua c� l?n ki?m tra n�o</strong><span>B?nh nh�n n�y chua c� d? li?u d? xem x�t.</span></div>}
    {checks.length > 0 && <div className="field review-select"><label htmlFor="check_select">L?n ki?m tra</label><select id="check_select" value={selectedCheckId ?? ""} onChange={(e) => setSelectedCheckId(e.target.value)}>{checks.map((c) => <option key={c.id} value={c.id}>{new Date(c.thoi_gian_kiem_tra).toLocaleString("vi-VN")}{c.co_canh_bao_nang ? " - Nghi�m tr?ng" : ""}{c.trang_thai_xac_nhan === "da_xac_nhan" ? " (d� x�c nh?n)" : ""}</option>)}</select></div>}
    {detail?.explanations?.map((e, idx) => <AlertCard key={idx} thuocA={e.thuoc_a} thuocB={e.thuoc_b} severity={e.muc_do} description={e.giai_thich} source={e.nguon_trich_dan} management={e.xu_tri} />)}
    <Disclaimer />
    {selectedCheckId && <section className="review-form panel"><div className="section__header"><h2 className="section__title"><MaterialIcon name="edit_note" size={20} /> Ghi nh?n x�t chuy�n m�n</h2></div><div className="field"><label htmlFor="ghi_chu">Ghi ch� c?a du?c si</label><textarea id="ghi_chu" rows={4} value={ghiChu} onChange={(e) => setGhiChu(e.target.value)} placeholder="V� d?: D� tu v?n b?nh nh�n trao d?i v?i b�c si di?u tr?..." /></div><button className="btn-block" onClick={handleConfirm} disabled={submitting}>{submitting ? <><span className="spinner spinner--sm" /> Dang luu...</> : <><MaterialIcon name="check_circle" size={20} /> X�c nh?n d� xem x�t</>}</button>{submitted && <p className="success-text"><MaterialIcon name="check_circle" size={18} /> D� x�c nh?n th�nh c�ng</p>}</section>}
  </main>;
}

export default function PharmacistReviewPage() { return <Suspense fallback={<main><div className="loading-row"><span className="spinner" /> Dang t?i...</div></main>}><ReviewContent /></Suspense>; }
