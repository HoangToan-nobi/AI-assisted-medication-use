"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MaterialIcon from "@/components/MaterialIcon";
import { getPharmacists, listPatientChecks, requestReview, type PharmacistSummary } from "@/lib/api";

type PharmacistReviewPromptProps = {
  checkId: string;
  token?: string;
  // Cần để tự tra lại trạng thái xác nhận thật của lần kiểm tra này (không chỉ
  // dựa vào state cục bộ "assigned" - state đó mất ngay khi rời trang/reload).
  patientId?: string;
  onAssigned?: () => void;
};

type KnownStatus = "chua_xac_nhan" | "cho_xac_nhan" | "da_xac_nhan";

// Gợi ý gửi lần kiểm tra hiện tại cho dược sĩ xem lại - tách từ check-result/page.tsx
// để dùng lại được ở cả trang chi tiết lịch sử lẫn popup tương tác nghiêm trọng.
export default function PharmacistReviewPrompt({ checkId, token, patientId, onAssigned }: PharmacistReviewPromptProps) {
  const [showPharmacists, setShowPharmacists] = useState(false);
  const [pharmacists, setPharmacists] = useState<PharmacistSummary[]>([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [assigned, setAssigned] = useState(false);
  const [knownStatus, setKnownStatus] = useState<KnownStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(Boolean(token && patientId));

  // Hỏi backend xem lần kiểm tra này đã từng được gửi/xác nhận chưa, để không
  // hỏi lại "bạn có muốn nhờ dược sĩ..." mỗi khi vào lại trang (reload, chuyển
  // tab rồi quay lại) sau khi đã lỡ gửi yêu cầu trong một lượt xem trước đó.
  useEffect(() => {
    if (!token || !patientId) { setStatusLoading(false); return; }
    let cancelled = false;
    setStatusLoading(true);
    listPatientChecks(patientId, token)
      .then((checks) => {
        if (cancelled) return;
        const match = checks.find((c) => c.id === checkId);
        setKnownStatus((match?.trang_thai_xac_nhan as KnownStatus) ?? "chua_xac_nhan");
      })
      .catch(() => { if (!cancelled) setKnownStatus("chua_xac_nhan"); })
      .finally(() => { if (!cancelled) setStatusLoading(false); });
    return () => { cancelled = true; };
  }, [checkId, token, patientId]);

  async function handleShowPharmacists() {
    setShowPharmacists(true);
    try { setPharmacists(await getPharmacists(token as string)); } catch { /* để trống, người dùng có thể thử lại */ }
  }

  async function handleAssign(pharmacistId: string) {
    setAssigningId(pharmacistId);
    try {
      await requestReview(checkId, pharmacistId, token as string);
      setAssigned(true);
      setShowPharmacists(false);
      onAssigned?.();
    } catch {
      alert("Lỗi khi gửi yêu cầu");
    } finally {
      setAssigningId(null);
    }
  }

  if (!token) {
    return (
      <div className="pharmacist-prompt">
        <p className="pharmacist-prompt__title">Bạn có muốn nhờ dược sĩ xác nhận lại tương tác thuốc này không?</p>
        <Link href="/" className="guest-login-link">Đăng nhập để gửi yêu cầu cho dược sĩ</Link>
      </div>
    );
  }

  if (statusLoading) {
    return (
      <div className="pharmacist-prompt pharmacist-prompt--loading">
        <span className="spinner spinner--sm" /> Đang kiểm tra trạng thái gửi dược sĩ...
      </div>
    );
  }

  if (assigned || knownStatus === "cho_xac_nhan") {
    return (
      <div className="pharmacist-prompt--done">
        <MaterialIcon name="check_circle" size={20} /> Đã gửi yêu cầu xem xét cho dược sĩ thành công! Dược sĩ sẽ xem xét và phản hồi sớm nhất.
      </div>
    );
  }

  if (knownStatus === "da_xac_nhan") {
    return (
      <div className="pharmacist-prompt--confirmed">
        <MaterialIcon name="check_circle" size={20} /> Dược sĩ đã xem xét và xác nhận tương tác này.
      </div>
    );
  }

  return (
    <div className="pharmacist-prompt">
      <p className="pharmacist-prompt__title">Bạn có muốn nhờ dược sĩ xác nhận lại tương tác thuốc này không?</p>
      {!showPharmacists ? (
        <button type="button" className="pharmacist-prompt__cta" onClick={() => void handleShowPharmacists()}>Nhờ dược sĩ xác nhận</button>
      ) : (
        <div className="pharmacist-prompt__list">
          {pharmacists.length === 0 ? <p className="pharmacist-prompt__loading">Đang tải danh sách dược sĩ...</p> : pharmacists.map((p) => (
            <div className="pharmacist-prompt__item" key={p.id}>
              <div>
                <div className="pharmacist-prompt__name">{p.ho_ten}</div>
                {p.noi_cong_tac && <div className="pharmacist-prompt__place"><MaterialIcon name="location_on" size={14} />{p.noi_cong_tac}</div>}
              </div>
              <button type="button" className="pharmacist-prompt__assign" disabled={assigningId === p.id} onClick={() => void handleAssign(p.id)}>
                {assigningId === p.id ? "Đang gửi..." : "Gửi yêu cầu"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
