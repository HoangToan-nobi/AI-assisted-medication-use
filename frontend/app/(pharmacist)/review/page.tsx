"use client";

<<<<<<< HEAD
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import InteractionGraphExplorer from "@/components/graph/InteractionGraphExplorer";
import {
  ApiError,
  getInteractionCheckDetail,
  getPatientProfile,
  listPatientMedications,
  listPharmacistRequests,
  submitPharmacistReview,
  type AgentCheckResult,
  type MedicationItem,
  type PatientProfileInfo,
} from "@/lib/api";
import { getSession } from "@/lib/auth";
import { productNamesFromExplanations } from "@/lib/interactionGraph";
import type { Prescription } from "@/lib/prescription";
=======
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, getInteractionCheckDetail, listPatientChecksForPharmacist, submitPharmacistReview, type AgentCheckResult, type InteractionCheckSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";
>>>>>>> origin/main

function ReviewContent() {
  const router = useRouter();
  const checkId = useSearchParams().get("checkId");
  const session = getSession();
<<<<<<< HEAD
  const [patientName, setPatientName] = useState<string | null>(null);
  const [profile, setProfile] = useState<PatientProfileInfo | null>(null);
  const [medications, setMedications] = useState<MedicationItem[]>([]);
=======
  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);
>>>>>>> origin/main
  const [detail, setDetail] = useState<AgentCheckResult | null>(null);
  const [ghiChu, setGhiChu] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
<<<<<<< HEAD
    if (!session || !checkId) return;
    
    setLoading(true);
    // Fetch requests to get patient info, then fetch profile/meds
    listPharmacistRequests(session.accessToken).then(requests => {
      const req = requests.find(r => r.check_id === checkId);
      if (req) {
        setPatientName(req.patient_name);
        Promise.all([
          listPatientMedications(req.patient_id, session.accessToken),
          getPatientProfile(req.patient_id, session.accessToken)
        ]).then(([meds, profileInfo]) => {
          setMedications(meds);
          setProfile(profileInfo);
        }).catch(err => console.error(err));
      }
    }).catch(err => console.error(err));

    getInteractionCheckDetail(checkId, session.accessToken)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được chi tiết lần kiểm tra"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkId]);

  // Dược sĩ xem lại cùng đúng graph phân cấp như bệnh nhân/tab tra cứu - dựng 1
  // "đơn thuốc" tổng hợp từ danh sách thuốc xuất hiện trong các cặp giải thích
  // (không có thông tin đơn thuốc gốc để tách theo đơn).
  const prescriptions: Prescription[] = useMemo(() => {
    if (!detail?.explanations) return [];
    const names = productNamesFromExplanations(detail.explanations);
    return [{ id: "review-check", label: "Thuốc đã kiểm tra", drugs: names.map((name) => ({ name, known: true })) }];
  }, [detail]);

  async function handleConfirm() {
    if (!session || !checkId) return;
    setSubmitting(true); setError(null);
    try {
      await submitPharmacistReview(checkId, ghiChu, session.accessToken);
      setSubmitted(true);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Không xác nhận được"); }
    finally { setSubmitting(false); }
  }

  if (!session) return null;
  if (!checkId) {
    return (
      <main>
        <div className="empty-state">
          <MaterialIcon name="search" size={40} />
          <strong>Không tìm thấy yêu cầu</strong>
          <span>Vui lòng chọn yêu cầu xét duyệt từ bảng điều khiển.</span>
          <button onClick={() => router.push("/pharmacist-dashboard")}>Về trang chủ</button>
        </div>
      </main>
    );
  }

  return (
    <main>
      <div className="page-header page-header--in-content">
        <button className="page-header__back" onClick={() => router.push("/pharmacist-dashboard")} aria-label="Quay lại">
          <MaterialIcon name="arrow_back" size={22} />
        </button>
        <div>
          <p className="eyebrow">XEM XÉT CHUYÊN MÔN</p>
          <h1 className="page-header__title">{patientName ? `Hồ sơ: ${patientName}` : "Chi tiết cảnh báo"}</h1>
        </div>
      </div>

      {loading && <div className="loading-row"><span className="spinner" /> Đang tải...</div>}
      {error && <p className="error-text" role="alert">{error}</p>}

      <div className="review-layout">
        <div className="review-layout__main">
          {!loading && (
        <section className="panel profile-medications">
          <div className="dashboard-section__header"><h2>Hồ sơ bệnh nhân</h2></div>
          {(profile?.ngay_sinh || profile?.benh_nen_ghi_chu) ? (
            <div className="field" style={{ marginBottom: 16 }}>
              {profile?.ngay_sinh && <p><strong>Ngày sinh:</strong> {profile.ngay_sinh}</p>}
              {profile?.benh_nen_ghi_chu && <p><strong>Bệnh nền / ghi chú:</strong> {profile.benh_nen_ghi_chu}</p>}
            </div>
          ) : (
            <p className="empty-state__hint">Bệnh nhân chưa cập nhật thông tin cá nhân.</p>
          )}
          {medications.length === 0 && <p className="empty-state__hint">Chưa có thuốc nào trong hồ sơ.</p>}
          {medications.map((item) => (
            <article className="profile-medication" key={item.id}>
              <span className="profile-medication__icon"><MaterialIcon name="medication" size={22} /></span>
              <div>
                <strong>{item.ten_thuoc}</strong>
                <p>{item.ngay_bat_dau ? `Bắt đầu từ ${item.ngay_bat_dau}` : "Mới thêm"}</p>
              </div>
            </article>
          ))}
        </section>
      )}


      {detail && prescriptions.length > 0 && (
        <InteractionGraphExplorer
          result={{
            explanations: detail.explanations ?? [],
            has_severe: detail.has_severe ?? false,
            has_unclassified: detail.has_unclassified ?? false,
            product_explanations: detail.product_explanations ?? [],
            prescription_explanations: detail.prescription_explanations ?? [],
          }}
          prescriptions={prescriptions}
          audience="pharmacist"
        />
      )}
          <Disclaimer />
        </div>

        <div className="review-layout__sidebar">
          {checkId && (
            <section className="review-form panel" style={{ margin: 0 }}>
              <div className="section__header"><h2 className="section__title"><MaterialIcon name="edit_note" size={20} /> Ghi nhận xét chuyên môn</h2></div>
              <div className="field">
                <label htmlFor="ghi_chu">Ghi chú của dược sĩ</label>
                <textarea id="ghi_chu" rows={4} value={ghiChu} onChange={(e) => setGhiChu(e.target.value)} placeholder="Ví dụ: Đã tư vấn bệnh nhân, trao đổi với bác sĩ điều trị..." />
              </div>
              <button className="btn-block" onClick={handleConfirm} disabled={submitting}>
                {submitting ? <><span className="spinner spinner--sm" /> Đang lưu...</> : <><MaterialIcon name="check_circle" size={20} /> Xác nhận đã xem xét</>}
              </button>
              {submitted && <p className="success-text"><MaterialIcon name="check_circle" size={18} /> Đã xác nhận thành công</p>}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

export default function PharmacistReviewPage() {
  return (
    <Suspense fallback={<main><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}>
      <ReviewContent />
    </Suspense>
  );
}
=======
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
>>>>>>> origin/main
