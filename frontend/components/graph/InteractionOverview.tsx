"use client";

import { useMemo, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import type { MedicationCheckResponse } from "@/lib/api";
import { buildPrescriptionGraph, buildProductGraph, withDataOnly } from "@/lib/interactionGraph";
import { drugOrigins, mergedDrugNames, type Prescription } from "@/lib/prescription";
import GraphPairList, { type GraphPairItem } from "./GraphPairList";
import InteractionGraphView, { type GraphEdgeVM, type GraphNodeVM } from "./InteractionGraphView";
import SeverityCountStrip from "./SeverityCountStrip";

type InteractionOverviewProps = {
  result: MedicationCheckResponse;
  prescriptions: Prescription[];
  // Mở lại popup gợi ý nhờ dược sĩ ở nơi khác (nếu có).
  onReopenSeverePopup?: () => void;
};

// Kết quả cho luồng bệnh nhân: không còn phân cấp drill-down (đơn -> thuốc ->
// hoạt chất) như InteractionGraphExplorer (vẫn dùng cho dược sĩ) - chỉ còn 1 đồ
// thị (nút = đơn thuốc nếu so nhiều đơn, ngược lại = thuốc) + 1 đoạn tóm tắt tổng
// quan do LLM sinh (result.overview), và 1 nút bấm để bung/ẩn danh sách chi tiết
// TỪNG CẶP THUỐC-THUỐC (không còn hoạt chất-hoạt chất hay đơn-đơn nữa).
export default function InteractionOverview({ result, prescriptions, onReopenSeverePopup }: InteractionOverviewProps) {
  const boardMode = prescriptions.length > 1;
  const [expanded, setExpanded] = useState(false);

  const origins = useMemo(() => drugOrigins(prescriptions), [prescriptions]);
  const dataExplanations = useMemo(() => withDataOnly(result.explanations), [result]);
  const productEdges = useMemo(
    () => buildProductGraph(mergedDrugNames(prescriptions), dataExplanations),
    [prescriptions, dataExplanations]
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

  const nodes: GraphNodeVM[] = boardMode
    ? prescriptions.map((p, i) => ({ id: `rx-${i}`, label: p.label, groupId: `rx-${i}` }))
    : mergedDrugNames(prescriptions).map((name) => ({ id: name, label: name, groupId: name }));

  const edges: GraphEdgeVM[] = boardMode
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

  // Chi tiết luôn ở cấp thuốc-với-thuốc, bất kể graph phía trên đang gộp theo đơn
  // hay không - đúng yêu cầu "chỉ còn hiện chi tiết tương tác thuốc với thuốc".
  const pairItems: GraphPairItem[] = productEdges.map((e) => {
    const backendItem = productExplanationByPair.get([e.productA.toLowerCase(), e.productB.toLowerCase()].sort().join("::"));
    return {
      id: `${e.productA}::${e.productB}`,
      thuocA: e.productA,
      thuocB: e.productB,
      severity: e.muc_do,
      description: backendItem?.giai_thich ?? "",
      source: backendItem?.nguon_trich_dan ?? "",
      hasIncompletePair: e.hasIncompletePair,
    };
  });

  return (
    <section className="interaction-result panel">
      <div className="interaction-result__header">
        <div><p className="eyebrow">ĐỒ THỊ TƯƠNG TÁC</p><h2>{title}</h2></div>
        <span className={result.has_severe ? "result-pill result-pill--danger" : result.has_unclassified ? "result-pill result-pill--unknown" : "result-pill"}>
          {result.has_severe ? "Cần lưu ý" : result.has_unclassified ? "Chưa cập nhật" : "An toàn"}
        </span>
      </div>

      <InteractionGraphView nodes={nodes} edges={edges} groups={[]} ariaLabel={title} />

      {result.overview && (
        <div className="interaction-overview__summary">
          <p className="eyebrow">TÓM TẮT TỔNG QUAN</p>
          <p>{result.overview.giai_thich}</p>
        </div>
      )}

      <SeverityCountStrip edges={productEdges} />

      {pairItems.length > 0 && (
        <button type="button" className="interaction-pairs__toggle" onClick={() => setExpanded((v) => !v)}>
          <MaterialIcon name={expanded ? "visibility_off" : "visibility"} size={17} />
          {expanded ? "Ẩn chi tiết tương tác" : `Xem chi tiết ${pairItems.length} cặp tương tác thuốc`}
        </button>
      )}
      {expanded && pairItems.length > 0 && (
        <GraphPairList items={pairItems} onReopenSeverePopup={onReopenSeverePopup} />
      )}
      {pairItems.length === 0 && nodes.length > 0 && (
        <div className="interaction-alert interaction-alert--empty"><MaterialIcon name="info" size={20} /><span>Không tìm thấy tương tác nào trong cơ sở dữ liệu cho lựa chọn hiện tại.</span></div>
      )}
    </section>
  );
}
