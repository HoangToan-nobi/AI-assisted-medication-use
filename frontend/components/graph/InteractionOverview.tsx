"use client";

import { useMemo, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import PharmacistReviewPrompt from "@/components/PharmacistReviewPrompt";
import type { MedicationCheckResponse, Severity } from "@/lib/api";
import type { Session } from "@/lib/auth";
import { buildPrescriptionGraph, buildProductGraph, withDataOnly } from "@/lib/interactionGraph";
import { drugOrigins, isCrossPrescription, mergedDrugNames, type Prescription } from "@/lib/prescription";
import GraphPairList, { type GraphPairItem } from "./GraphPairList";
import InteractionGraphView, { type GraphEdgeVM, type GraphNodeVM } from "./InteractionGraphView";
import SeverityCountStrip from "./SeverityCountStrip";
import MediFox from "@/components/MediFox";

type InteractionOverviewProps = {
  result: MedicationCheckResponse;
  prescriptions: Prescription[];
  // Mở lại popup gợi ý nhờ dược sĩ ở nơi khác (nếu có).
  session: Session | null;
  // "pharmacist": bàn cân tra cứu độc lập của dược sĩ (pharmacist-lookup) - ưu
  // tiên bản giọng điệu khoa học/chuyên nghiệp (giai_thich_duoc_si) khi có, và ẩn
  // hẳn khung "Nhờ dược sĩ xác nhận" (dành cho bệnh nhân, vô nghĩa với chính dược
  // sĩ). Mặc định "patient" - đúng hành vi cũ.
  audience?: "patient" | "pharmacist";
};

function pickText(item: { giai_thich: string; giai_thich_duoc_si?: string } | undefined, audience: "patient" | "pharmacist"): string {
  if (!item) return "";
  return audience === "pharmacist" ? item.giai_thich_duoc_si ?? item.giai_thich : item.giai_thich;
}

// Kết quả cho luồng bệnh nhân: không còn phân cấp drill-down (đơn -> thuốc ->
// hoạt chất) như InteractionGraphExplorer (vẫn dùng cho dược sĩ) - chỉ còn 1 đồ
// thị (nút = đơn thuốc nếu so nhiều đơn, ngược lại = thuốc) + 1 đoạn tóm tắt tổng
// quan do LLM sinh (result.overview), và 1 nút bấm để bung/ẩn danh sách chi tiết
// TỪNG CẶP THUỐC-THUỐC (không còn hoạt chất-hoạt chất hay đơn-đơn nữa). Cũng dùng
// lại cho bàn cân tra cứu độc lập của dược sĩ (audience="pharmacist").
export default function InteractionOverview({ result, prescriptions, session, audience = "patient" }: InteractionOverviewProps) {
  const boardMode = prescriptions.length > 1;
  const [expanded, setExpanded] = useState(false);

  const origins = useMemo(() => drugOrigins(prescriptions), [prescriptions]);
  const dataExplanations = useMemo(() => withDataOnly(result.explanations), [result]);
  const allProductEdges = useMemo(
    () => buildProductGraph(mergedDrugNames(prescriptions), dataExplanations),
    [prescriptions, dataExplanations]
  );
  // Có từ 2 đơn trở lên: chỉ giữ cặp thuốc-thuốc GIỮA các đơn khác nhau - bỏ tương
  // tác trong cùng 1 đơn khỏi thống kê/chi tiết/tóm tắt, vì bệnh nhân so nhiều đơn
  // chỉ muốn biết việc gộp chung có phát sinh rủi ro mới gì, không phải rà lại từng
  // đơn đang dùng riêng lẻ (khớp với result.overview do backend đã sinh cùng logic).
  const productEdges = useMemo(
    () => (boardMode ? allProductEdges.filter((e) => isCrossPrescription(origins, e.productA, e.productB)) : allProductEdges),
    [boardMode, allProductEdges, origins]
  );
  const prescriptionEdges = useMemo(
    () => (boardMode ? buildPrescriptionGraph(productEdges, origins) : []),
    [boardMode, productEdges, origins]
  );

  const productExplanationByPair = useMemo(() => {
    const map = new Map<string, NonNullable<typeof result.product_explanations>[number]>();
    for (const item of result.product_explanations ?? []) {
      map.set([item.thuoc_a.toLowerCase(), item.thuoc_b.toLowerCase()].sort().join("::"), item);
    }
    return map;
  }, [result]);

  const title = boardMode ? "Tương tác giữa các đơn thuốc" : "Tương tác giữa các thuốc";

  const allNodes: GraphNodeVM[] = boardMode
    ? prescriptions.map((p, i) => ({ id: `rx-${i}`, label: p.label, groupId: `rx-${i}` }))
    : mergedDrugNames(prescriptions).map((name) => ({ id: name, label: name, groupId: name }));

  const allEdges: GraphEdgeVM[] = boardMode
    ? prescriptionEdges.map((e) => ({
        id: `rx-${e.prescriptionAIndex}::rx-${e.prescriptionBIndex}`,
        sourceId: `rx-${e.prescriptionAIndex}`,
        targetId: `rx-${e.prescriptionBIndex}`,
        muc_do: e.muc_do,
        hasIncompletePair: e.hasIncompletePair,
      }))
    : productEdges.map((e) => ({
        id: `${e.productA}::${e.productB}`,
        sourceId: e.productA,
        targetId: e.productB,
        muc_do: e.muc_do,
        hasIncompletePair: e.hasIncompletePair,
      }));

  // Đồ thị từ 6 node trở lên: bớt rối bằng cách chỉ giữ cạnh ĐÃ phân loại mức độ
  // (bỏ cạnh "chưa phân loại"), rồi bỏ luôn các node không còn cạnh nào sau khi
  // lọc. Từ 5 node trở xuống vẫn hiển thị đầy đủ như trước (đồ thị đã đủ gọn).
  const shouldSimplifyGraph = allNodes.length >= 6;
  const edges = shouldSimplifyGraph ? allEdges.filter((e) => e.muc_do !== "chua_phan_loai") : allEdges;
  const nodes = shouldSimplifyGraph
    ? (() => {
        const connectedIds = new Set(edges.flatMap((e) => [e.sourceId, e.targetId]));
        return allNodes.filter((n) => connectedIds.has(n.id));
      })()
    : allNodes;

  // Chi tiết luôn ở cấp thuốc-với-thuốc, bất kể graph phía trên đang gộp theo đơn
  // hay không - đúng yêu cầu "chỉ còn hiện chi tiết tương tác thuốc với thuốc".
  const rawPairItems: GraphPairItem[] = productEdges.map((e) => {
    const backendItem = productExplanationByPair.get([e.productA.toLowerCase(), e.productB.toLowerCase()].sort().join("::"));
    return {
      id: `${e.productA}::${e.productB}`,
      thuocA: e.productA,
      thuocB: e.productB,
      severity: e.muc_do,
      description: pickText(backendItem, audience),
      source: backendItem?.nguon_trich_dan ?? "",
      hasIncompletePair: e.hasIncompletePair,
      // Chỉ dược sĩ mới có (backend đã tự ẩn với bệnh nhân) - bản dịch nguyên văn
      // (không qua diễn giải) từ CSDL của mô tả tương tác + khuyến nghị xử trí.
      scientificDescription: backendItem?.mo_ta_dich,
      management: backendItem?.xu_tri_dich,
    };
  });

  // Sắp xếp thẻ chi tiết theo mức độ nghiêm trọng -> trung bình -> nhẹ. Các cặp
  // "chưa phân loại" không xếp xen kẽ theo severity mà GỘP CHUNG thành 1 thẻ duy
  // nhất ở cuối danh sách - tránh lặp lại nhiều thẻ gần như giống hệt nhau khi
  // chưa có đủ dữ liệu phân loại mức độ.
  const SEVERITY_ORDER: Record<Severity, number> = { nang: 3, trung_binh: 2, nhe: 1, chua_phan_loai: 0 };
  const classifiedPairItems = rawPairItems
    .filter((item) => item.severity !== "chua_phan_loai")
    .sort((a, b) => SEVERITY_ORDER[b.severity ?? "chua_phan_loai"] - SEVERITY_ORDER[a.severity ?? "chua_phan_loai"]);
  const unclassifiedPairItems = rawPairItems.filter((item) => item.severity === "chua_phan_loai");
  const mergedUnclassifiedItem: GraphPairItem | null = unclassifiedPairItems.length > 0 ? {
    id: "unclassified-merged",
    severity: "chua_phan_loai",
    description: `Chưa có đủ dữ liệu để phân loại mức độ tương tác giữa ${unclassifiedPairItems.length} cặp thuốc: ${unclassifiedPairItems.map((i) => `${i.thuocA} + ${i.thuocB}`).join(", ")}.`,
    source: "",
    hasIncompletePair: false,
    mergedPairIds: unclassifiedPairItems.map((i) => i.id),
  } : null;
  const pairItems: GraphPairItem[] = mergedUnclassifiedItem ? [...classifiedPairItems, mergedUnclassifiedItem] : classifiedPairItems;

  return (
    <>
      {audience === "pharmacist" && result.has_severe && (
        <aside className="interaction-mascot-note interaction-mascot-note--alert">
          <MediFox variant="alert" className="interaction-mascot-note__image" />
          <div>
            <strong>Cáo Medi nhắc bạn cần lưu ý</strong>
            <p>Hãy đọc kỹ cảnh báo và trao đổi với bác sĩ hoặc dược sĩ trước khi dùng thuốc.</p>
          </div>
        </aside>
      )}
      <section className="interaction-result panel">
      <div className="interaction-result__header">
        <div><p className="eyebrow">ĐỒ THỊ TƯƠNG TÁC</p><h2>{title}</h2></div>
        <span className={result.has_severe ? "result-pill result-pill--danger" : result.has_unclassified ? "result-pill result-pill--unknown" : "result-pill"}>
          {result.has_severe ? "Cần lưu ý" : result.has_unclassified ? "Chưa cập nhật" : "An toàn"}
        </span>
      </div>

      <InteractionGraphView nodes={nodes} edges={edges} groups={[]} ariaLabel={title} />

      <SeverityCountStrip edges={productEdges} />

      {result.overview && (
        <div className="interaction-overview__summary">
          <p className="eyebrow">TÓM TẮT TỔNG QUAN</p>
          <p>{result.overview.giai_thich}</p>
        </div>
      )}

      {audience === "patient" && (
        <section className="pharmacist-review-section">
          <PharmacistReviewPrompt checkId={result.interaction_check_id} token={session?.accessToken} patientId={session?.userId} />
        </section>
      )}

      {rawPairItems.length > 0 && (
        <button type="button" className="interaction-pairs__toggle" onClick={() => setExpanded((v) => !v)}>
          <MaterialIcon name={expanded ? "visibility_off" : "visibility"} size={17} />
          {expanded ? "Ẩn chi tiết tương tác" : `Xem chi tiết ${rawPairItems.length} cặp tương tác thuốc`}
        </button>
      )}
      {expanded && pairItems.length > 0 && (
        <GraphPairList items={pairItems} />
      )}
      {pairItems.length === 0 && allNodes.length > 0 && (
        <div className="interaction-alert interaction-alert--empty"><MaterialIcon name="info" size={20} /><span>Không tìm thấy tương tác nào trong cơ sở dữ liệu cho lựa chọn hiện tại.</span></div>
      )}
      </section>
    </>
  );
}
