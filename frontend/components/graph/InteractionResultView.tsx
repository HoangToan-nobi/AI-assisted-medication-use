"use client";

import type { MedicationCheckResponse } from "@/lib/api";
import type { Session } from "@/lib/auth";
import type { Prescription } from "@/lib/prescription";
import InteractionOverview from "./InteractionOverview";
import MediFox from "@/components/MediFox";

type InteractionResultViewProps = {
  result: MedicationCheckResponse;
  prescriptions: Prescription[];
  session: Session | null;
};

// Dùng ở tab "Tra cứu tương tác" (kết quả vừa tính xong): bọc InteractionOverview,
// vốn tự hiện khung "Nhờ dược sĩ xác nhận" bên trong nó cho MỌI lần tra cứu (không
// còn chỉ dành riêng cho tương tác nghiêm trọng như trước).
export default function InteractionResultView({ result, prescriptions, session }: InteractionResultViewProps) {
  return <>
    <aside className={`interaction-mascot-note ${result.has_severe ? "interaction-mascot-note--alert" : ""}`}>
      <MediFox variant="alert" className="interaction-mascot-note__image" />
      <div>
        <strong>{result.has_severe ? "Cáo Medi nhắc bạn cần lưu ý" : "Cáo Medi đã kiểm tra xong"}</strong>
        <p>{result.has_severe ? "Hãy đọc kỹ cảnh báo và hỏi dược sĩ hoặc bác sĩ trước khi dùng thuốc." : "Kết quả không thay thế tư vấn trực tiếp từ bác sĩ hoặc dược sĩ."}</p>
      </div>
    </aside>
    <InteractionOverview result={result} prescriptions={prescriptions} session={session} />
  </>;
}
