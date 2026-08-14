import MaterialIcon from "@/components/MaterialIcon";
import PharmacistReviewPrompt from "@/components/PharmacistReviewPrompt";
import type { Session } from "@/lib/auth";

type SevereInteractionPopupProps = {
  checkId: string;
  session: Session | null;
  onClose: () => void;
};

// Popup gợi ý (đóng được) khi kết quả phân tích có tương tác nghiêm trọng - sống ở
// component cha của view-stack nên không mất khi drill-down/quay lại giữa các cấp.
export default function SevereInteractionPopup({ checkId, session, onClose }: SevereInteractionPopupProps) {
  return (
    <div className="tt-severe-popup" role="alert">
      <button type="button" className="tt-severe-popup__close" onClick={onClose} aria-label="Đóng thông báo">
        <MaterialIcon name="close" size={18} />
      </button>
      <div className="tt-severe-popup__header"><MaterialIcon name="warning" size={22} filled /><strong>Phát hiện tương tác nghiêm trọng</strong></div>
      <PharmacistReviewPrompt checkId={checkId} token={session?.accessToken} patientId={session?.userId} />
    </div>
  );
}
