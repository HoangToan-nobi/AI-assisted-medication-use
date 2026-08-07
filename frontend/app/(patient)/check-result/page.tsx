"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, getPatientCheckDetail, type MedicationCheckResponse } from "@/lib/api";
import { getSession } from "@/lib/auth";

function CheckResultContent() {
  const router = useRouter();
  const checkId = useSearchParams().get("checkId");
  const session = getSession();
  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      <section className={`result-hero ${result.has_severe ? "result-hero--severe" : result.has_unclassified ? "result-hero--unknown" : "result-hero--safe"}`}><span className="result-hero__icon"><MaterialIcon name={result.has_severe ? "warning" : result.has_unclassified ? "help" : "verified"} size={30} filled /></span><div><p className="eyebrow">TÓM TẮT PHÂN TÍCH</p><h2>{result.has_severe ? "Phát hiện cảnh báo nghiêm trọng" : result.has_unclassified ? "Chưa cập nhật đầy đủ dữ liệu" : "Chưa phát hiện cảnh báo nghiêm trọng"}</h2><p>{result.has_severe ? "Vui lòng liên hệ dược sĩ hoặc bác sĩ để được tư vấn kịp thời." : result.has_unclassified ? "Một số tương tác chưa có đủ dữ liệu để kết luận an toàn." : "Hãy tiếp tục sử dụng thuốc theo đúng hướng dẫn chuyên môn."}</p></div></section>
      {result.has_unclassified && <div className="info-banner"><MaterialIcon name="info" size={20} /><span>Có ít nhất một cặp thuốc chưa được cập nhật mức độ nghiêm trọng. Hãy hỏi dược sĩ hoặc bác sĩ.</span></div>}
      <div className="section__header result-list-heading"><h2 className="section__title"><MaterialIcon name="fact_check" size={20} /> Chi tiết tương tác</h2></div>
      {result.explanations.map((e, idx) => <AlertCard key={idx} thuocA={e.thuoc_a} thuocB={e.thuoc_b} severity={e.muc_do} description={e.giai_thich} source={e.nguon_trich_dan} />)}
    </>}
    <Disclaimer />
    <button className="secondary btn-block" onClick={() => router.push("/history")}><MaterialIcon name="arrow_back" size={20} /> Về lịch sử kiểm tra</button>
  </main>;
}

export default function CheckResultPage() { return <Suspense fallback={<main><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}><CheckResultContent /></Suspense>; }
