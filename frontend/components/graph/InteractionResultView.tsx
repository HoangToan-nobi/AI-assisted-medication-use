"use client";

import type { MedicationCheckResponse } from "@/lib/api";
import type { Session } from "@/lib/auth";
import type { Prescription } from "@/lib/prescription";
import InteractionOverview from "./InteractionOverview";

type InteractionResultViewProps = {
  result: MedicationCheckResponse;
  prescriptions: Prescription[];
  session: Session | null;
};

// Dùng ở tab "Tra cứu tương tác" (kết quả vừa tính xong): bọc InteractionOverview,
// vốn tự hiện khung "Nhờ dược sĩ xác nhận" bên trong nó cho MỌI lần tra cứu (không
// còn chỉ dành riêng cho tương tác nghiêm trọng như trước).
export default function InteractionResultView({ result, prescriptions, session }: InteractionResultViewProps) {
  return <InteractionOverview result={result} prescriptions={prescriptions} session={session} />;
}
