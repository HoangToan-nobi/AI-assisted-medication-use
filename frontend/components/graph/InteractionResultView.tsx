"use client";

import { useEffect, useState } from "react";
import type { MedicationCheckResponse } from "@/lib/api";
import type { Session } from "@/lib/auth";
import type { Prescription } from "@/lib/prescription";
import InteractionOverview from "./InteractionOverview";
import SevereInteractionPopup from "./SevereInteractionPopup";

type InteractionResultViewProps = {
  result: MedicationCheckResponse;
  prescriptions: Prescription[];
  session: Session | null;
};

// Dùng ở tab "Tra cứu tương tác" (kết quả vừa tính xong): bọc InteractionOverview
// bằng popup gợi ý nhờ dược sĩ, có thể đóng rồi mở lại.
export default function InteractionResultView({ result, prescriptions, session }: InteractionResultViewProps) {
  const [popupDismissed, setPopupDismissed] = useState(false);

  useEffect(() => {
    setPopupDismissed(false);
  }, [result]);

  return (
    <>
      {result.has_severe && !popupDismissed && (
        <SevereInteractionPopup checkId={result.interaction_check_id} session={session} onClose={() => setPopupDismissed(true)} />
      )}
      <InteractionOverview
        result={result}
        prescriptions={prescriptions}
        onReopenSeverePopup={result.has_severe && popupDismissed ? () => setPopupDismissed(false) : undefined}
      />
    </>
  );
}
