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
type Step = "cta" | "list" | "form";

// Gợi ý gửi lần kiểm tra hiện tại cho dược sĩ xem lại - tách từ check-result/page.tsx
// để dùng lại được ở mọi nơi hiện kết quả (InteractionOverview render widget này
// cho MỌI lần tra cứu, không riêng gì tương tác nghiêm trọng).
export default function PharmacistReviewPrompt({ checkId, token, patientId, onAssigned }: PharmacistReviewPromptProps) {
  const [step, setStep] = useState<Step>("cta");
  const [pharmacists, setPharmacists] = useState<PharmacistSummary[]>([]);
  const [pharmacistsLoading, setPharmacistsLoading] = useState(false);
  const [selected, setSelected] = useState<PharmacistSummary | null>(null);
  const [attachProfile, setAttachProfile] = useState(true);
  const [manualName, setManualName] = useState("");
  const [manualDob, setManualDob] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
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
    setStep("list");
    setPharmacistsLoading(true);
    try { setPharmacists(await getPharmacists(token as string)); } catch { /* để trống, người dùng có thể thử lại */ }
    finally { setPharmacistsLoading(false); }
  }

  function handleSelectPharmacist(p: PharmacistSummary) {
    setSelected(p);
    setAttachProfile(true);
    setManualName(""); setManualDob(""); setManualNote("");
    setSubmitError(null);
    setStep("form");
  }

  async function handleSubmitRequest() {
    if (!selected) return;
    setSubmitting(true); setSubmitError(null);
    try {
      await requestReview(checkId, selected.id, token as string, {
        guiKemHoSo: attachProfile,
        tenNguoiDuocKiemTra: attachProfile ? undefined : manualName.trim() || undefined,
        ngaySinhNhapTay: attachProfile ? undefined : manualDob || undefined,
        ghiChuNhapTay: attachProfile ? undefined : manualNote.trim() || undefined,
      });
      setAssigned(true);
      onAssigned?.();
    } catch {
      setSubmitError("Lỗi khi gửi yêu cầu, vui lòng thử lại.");
    } finally {
      setSubmitting(false);
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

  if (step === "form" && selected) {
    return (
      <div className="pharmacist-prompt">
        <button type="button" className="pharmacist-prompt__back" onClick={() => setStep("list")}>
          <MaterialIcon name="arrow_back" size={16} /> Chọn dược sĩ khác
        </button>
        <p className="pharmacist-prompt__title">Gửi yêu cầu tới <strong>{selected.ho_ten}</strong></p>
        <div className="pharmacist-prompt__attach-toggle">
          <label>
            <input type="radio" name="attach-mode" checked={attachProfile} onChange={() => setAttachProfile(true)} />
            Gửi kèm hồ sơ cá nhân của tôi
          </label>
          <label>
            <input type="radio" name="attach-mode" checked={!attachProfile} onChange={() => setAttachProfile(false)} />
            Nhập thông tin khác (tra cứu hộ người khác)
          </label>
        </div>
        {!attachProfile && (
          <div className="pharmacist-prompt__manual-form">
            <div className="field"><label>Họ tên người được kiểm tra</label><input value={manualName} onChange={(e) => setManualName(e.target.value)} placeholder="Ví dụ: Nguyễn Văn A" /></div>
            <div className="field"><label>Ngày sinh</label><input type="date" value={manualDob} onChange={(e) => setManualDob(e.target.value)} /></div>
            <div className="field"><label>Ghi chú (bệnh nền, dị ứng...)</label><textarea rows={2} value={manualNote} onChange={(e) => setManualNote(e.target.value)} placeholder="Không bắt buộc" /></div>
          </div>
        )}
        {submitError && <p className="error-text" role="alert">{submitError}</p>}
        <button type="button" className="pharmacist-prompt__cta" disabled={submitting} onClick={() => void handleSubmitRequest()}>
          {submitting ? "Đang gửi..." : "Gửi yêu cầu"}
        </button>
      </div>
    );
  }

  return (
    <div className="pharmacist-prompt">
      <p className="pharmacist-prompt__title">Bạn có muốn nhờ dược sĩ xác nhận lại tương tác thuốc này không?</p>
      {step === "cta" ? (
        <button type="button" className="pharmacist-prompt__cta" onClick={() => void handleShowPharmacists()}>Nhờ dược sĩ xác nhận</button>
      ) : (
        <div className="pharmacist-prompt__list">
          {pharmacistsLoading ? <p className="pharmacist-prompt__loading">Đang tải danh sách dược sĩ...</p> : pharmacists.map((p) => (
            <button type="button" className="pharmacist-prompt__item" key={p.id} onClick={() => handleSelectPharmacist(p)}>
              <div>
                <div className="pharmacist-prompt__name">{p.ho_ten}</div>
                {p.noi_cong_tac && <div className="pharmacist-prompt__place"><MaterialIcon name="location_on" size={14} />{p.noi_cong_tac}</div>}
                <div className="pharmacist-prompt__bio">{p.mo_ta_ngan || "Chưa cập nhật thông tin"}</div>
              </div>
              <MaterialIcon name="chevron_right" size={18} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
