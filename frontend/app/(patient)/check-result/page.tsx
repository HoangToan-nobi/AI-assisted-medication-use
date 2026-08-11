"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, getPatientCheckDetail, getPharmacists, requestReview, type MedicationCheckResponse, type PharmacistSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";

function CheckResultContent() {
  const router = useRouter();
  const checkId = useSearchParams().get("checkId");
  const session = getSession();
  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [showPharmacists, setShowPharmacists] = useState(false);
  const [pharmacists, setPharmacists] = useState<PharmacistSummary[]>([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [assigned, setAssigned] = useState(false);

  const handleShowPharmacists = async () => {
    setShowPharmacists(true);
    try {
      const list = await getPharmacists(session!.accessToken);
      setPharmacists(list);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAssign = async (phId: string) => {
    const currentCheckId = checkId || result?.interaction_check_id;
    if (!currentCheckId) {
      alert("Lỗi: Không tìm thấy ID lần kiểm tra");
      return;
    }
    setAssigningId(phId);
    try {
      await requestReview(currentCheckId, phId, session!.accessToken);
      setAssigned(true);
      setShowPharmacists(false);
    } catch (err) {
      alert("Lỗi khi gửi yêu cầu");
    } finally {
      setAssigningId(null);
    }
  };

  useEffect(() => {
    if (!session) return;
    if (checkId) {
      getPatientCheckDetail(session.userId, checkId, session.accessToken)
        .then(setResult)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được kết quả"))
        .finally(() => setLoading(false));
      return;
    }
    const raw = window.sessionStorage.getItem("medguard_last_check");
    if (raw) setResult(JSON.parse(raw) as MedicationCheckResponse);
    else setError("Không có kết quả kiểm tra để hiển thị.");
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkId]);

  if (!session) return null;
  return <main className="check-result-page">
    <div className="page-header page-header--in-content"><button className="page-header__back" onClick={() => router.push("/history")} aria-label="Quay lại"><MaterialIcon name="arrow_back" size={22} /></button><div><p className="eyebrow">PHÂN TÍCH AN TOÀN</p><h1 className="page-header__title">Chi tiết kiểm tra tương tác</h1></div></div>
    {loading && <div className="loading-row"><span className="spinner" /> Đang tải kết quả...</div>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {!loading && result && <>
      <section className={`result-hero ${result.has_severe ? "result-hero--severe" : result.has_unclassified ? "result-hero--unknown" : "result-hero--safe"}`}>
        <span className="result-hero__icon"><MaterialIcon name={result.has_severe ? "warning" : result.has_unclassified ? "help" : "verified"} size={30} filled /></span>
        <div><p className="eyebrow">TÓM TẮT PHÂN TÍCH</p><h2>{result.has_severe ? "Phát hiện cảnh báo nghiêm trọng" : result.has_unclassified ? "Chưa cập nhật đầy đủ dữ liệu" : "Chưa phát hiện cảnh báo nghiêm trọng"}</h2><p>{result.has_severe ? "Vui lòng liên hệ dược sĩ hoặc bác sĩ để được tư vấn kịp thời." : result.has_unclassified ? "Một số tương tác chưa có đủ dữ liệu để kết luận an toàn." : "Hãy tiếp tục sử dụng thuốc theo đúng hướng dẫn chuyên môn."}</p></div>
      </section>
      
      {result.has_severe && !assigned && (
        <div style={{ marginTop: "16px", padding: "16px", background: "#fff", borderRadius: "8px", border: "1px solid #ffd8d8", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
          <p style={{ fontWeight: 600, color: "#d32f2f", marginBottom: "8px", fontSize: "15px" }}>Bạn có muốn nhờ dược sĩ xác nhận lại tương tác thuốc này không?</p>
          {!showPharmacists ? (
            <button onClick={handleShowPharmacists} style={{ background: "#d32f2f", color: "#fff", padding: "10px 16px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>Nhờ dược sĩ xác nhận</button>
          ) : (
            <div style={{ marginTop: "12px" }}>
              <p style={{ fontSize: "14px", marginBottom: "12px", color: "#444" }}>Chọn dược sĩ để gửi yêu cầu xem xét:</p>
              {pharmacists.length === 0 ? <p style={{fontSize:"13px", color:"#666"}}>Đang tải danh sách dược sĩ...</p> : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {pharmacists.map(p => (
                    <div key={p.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px", border: "1px solid #eee", borderRadius: "6px", background: "#fafafa" }}>
                      <div>
                        <div style={{ fontWeight: 600, color: "#1a2b4c" }}>{p.ho_ten}</div>
                        {p.noi_cong_tac && <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}><MaterialIcon name="location_on" size={14} style={{verticalAlign:"middle", marginRight:"4px"}}/>{p.noi_cong_tac}</div>}
                      </div>
                      <button onClick={() => handleAssign(p.id)} disabled={assigningId === p.id} style={{ padding: "8px 16px", borderRadius: "4px", background: assigningId === p.id ? "#ccc" : "#0056b3", color: "#fff", border: "none", cursor: "pointer", fontWeight: 600 }}>
                        {assigningId === p.id ? "Đang gửi..." : "Gửi yêu cầu"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {assigned && (
        <div style={{ marginTop: "16px", padding: "12px 16px", background: "#e8f5e9", color: "#2e7d32", borderRadius: "8px", display: "flex", gap: "8px", alignItems: "center", border: "1px solid #c8e6c9" }}>
          <MaterialIcon name="check_circle" size={20} /> Đã gửi yêu cầu xem xét cho dược sĩ thành công! Dược sĩ sẽ xem xét và phản hồi sớm nhất.
        </div>
      )}

      {result.has_unclassified && <div className="info-banner"><MaterialIcon name="info" size={20} /><span>Có ít nhất một cặp thuốc chưa được cập nhật mức độ nghiêm trọng. Hãy hỏi dược sĩ hoặc bác sĩ.</span></div>}
      <div className="section__header result-list-heading"><h2 className="section__title"><MaterialIcon name="fact_check" size={20} /> Chi tiết tương tác</h2></div>
      {result.explanations.map((e, idx) => <AlertCard key={idx} thuocA={e.thuoc_a} thuocB={e.thuoc_b} severity={e.muc_do} description={e.giai_thich} source={e.nguon_trich_dan} />)}
    </>}
    <Disclaimer />
    <button className="secondary btn-block" onClick={() => router.push("/history")}><MaterialIcon name="arrow_back" size={20} /> Về lịch sử kiểm tra</button>
  </main>;
}

export default function CheckResultPage() { return <Suspense fallback={<main><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}><CheckResultContent /></Suspense>; }
