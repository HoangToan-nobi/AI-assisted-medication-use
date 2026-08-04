"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import { ApiError, getPatientCheckDetail, type MedicationCheckResponse } from "@/lib/api";
import { getSession } from "@/lib/auth";

function CheckResultContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const checkId = searchParams.get("checkId");
  const session = getSession();

  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) return;

    if (checkId) {
      getPatientCheckDetail(session.userId, checkId, session.accessToken)
        .then(setResult)
        .catch((err) =>
          setError(err instanceof ApiError ? err.message : "Không tải được kết quả")
        )
        .finally(() => setLoading(false));
      return;
    }

    const raw = window.sessionStorage.getItem("medguard_last_check");
    if (raw) {
      setResult(JSON.parse(raw) as MedicationCheckResponse);
    } else {
      setError("Không có kết quả kiểm tra để hiển thị.");
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkId]);

  if (!session) return null;

  return (
    <main>
      <h1>Kết quả kiểm tra tương tác</h1>

      {loading && (
        <div className="loading-row">
          <span className="spinner" aria-hidden="true" />
          Đang tải kết quả...
        </div>
      )}
      {error && <p className="error-text">{error}</p>}

      {result?.has_severe && (
        <div className="urgent-banner">
          <span className="banner-icon" aria-hidden="true">
            🚨
          </span>
          <span>
            Phát hiện tương tác mức <strong>nghiêm trọng</strong>. Vui lòng liên hệ dược sĩ/bác sĩ
            ngay để được tư vấn kịp thời.
          </span>
        </div>
      )}

      {result?.has_unclassified && (
        <div className="info-banner">
          <span aria-hidden="true">ℹ️</span>
          <span>
            Có ít nhất 1 cặp thuốc chưa được DDInter phân loại mức độ nghiêm trọng — cần thận
            trọng và hỏi dược sĩ/bác sĩ.
          </span>
        </div>
      )}

      {result?.explanations.map((e, idx) => (
        <AlertCard
          key={idx}
          thuocA={e.thuoc_a}
          thuocB={e.thuoc_b}
          severity={e.muc_do}
          description={e.giai_thich}
          source={e.nguon_trich_dan}
        />
      ))}

      <Disclaimer />

      <button className="secondary" onClick={() => router.push("/dashboard")}>
        ← Về trang chủ
      </button>
    </main>
  );
}

export default function CheckResultPage() {
  return (
    <Suspense
      fallback={
        <main>
          <p>Đang tải...</p>
        </main>
      }
    >
      <CheckResultContent />
    </Suspense>
  );
}
