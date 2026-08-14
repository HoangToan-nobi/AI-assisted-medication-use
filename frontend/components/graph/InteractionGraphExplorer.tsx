"use client";

import { useEffect, useMemo, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import type { MedicationCheckResponse } from "@/lib/api";
import {
  assignGroupColors,
  buildIngredientGraph,
  buildPrescriptionGraph,
  buildProductGraph,
  drugEdgesBetweenPrescriptions,
  representativeExplanation,
  withDataOnly,
  type GraphGroup,
  type IngredientEdge,
  type ProductEdge,
} from "@/lib/interactionGraph";
import { drugOrigins, mergedDrugNames, type Prescription } from "@/lib/prescription";
import GraphPairList, { type GraphPairItem } from "./GraphPairList";
import InteractionGraphView, { type GraphEdgeVM, type GraphNodeVM } from "./InteractionGraphView";
import SeverityCountStrip from "./SeverityCountStrip";

type GraphLevel =
  | { kind: "prescriptions" }
  | { kind: "drugs"; rxIndexes: number[] }
  | { kind: "ingredients"; drugA: string; drugB: string };

// Chỉ cần đúng các field này để dựng đồ thị - để component dùng chung được cho cả
// MedicationCheckResponse (bệnh nhân) lẫn AgentCheckResult (dược sĩ, không có
// interaction_check_id vì endpoint xem lại của dược sĩ không trả field đó).
export type InteractionGraphExplorerResult = Pick<
  MedicationCheckResponse,
  "explanations" | "has_severe" | "has_unclassified" | "product_explanations" | "prescription_explanations"
>;

type InteractionGraphExplorerProps = {
  result: InteractionGraphExplorerResult;
  prescriptions: Prescription[];
  // "pharmacist" ưu tiên bản giọng điệu khoa học (giai_thich_duoc_si) khi có; mặc
  // định "patient" luôn dùng bản thân thiện (giai_thich) - đúng field bệnh nhân
  // nhận được từ backend (giai_thich_duoc_si đã bị lược bỏ với bệnh nhân).
  audience?: "patient" | "pharmacist";
};

function pickText(
  item: { giai_thich: string; giai_thich_duoc_si?: string } | undefined,
  audience: "patient" | "pharmacist"
): string {
  if (!item) return "";
  return audience === "pharmacist" ? item.giai_thich_duoc_si ?? item.giai_thich : item.giai_thich;
}

// Với 1 tên thuốc và đúng 2 chỉ số đơn đang so sánh, tìm đơn nào chứa thuốc đó để
// tô màu nhóm (dùng khi 1 thuốc chỉ thuộc 1 trong 2 đơn - trường hợp thông thường).
function groupIdForDrug(drugName: string, rxIndexes: number[], origins: Map<string, Set<number>>): string {
  const set = origins.get(drugName.toLowerCase());
  const match = set ? rxIndexes.find((i) => set.has(i)) : undefined;
  return `rx-${match ?? rxIndexes[0]}`;
}

// Danh sách tên thuốc (không trùng) thuộc về các đơn có chỉ số trong rxIndexes.
function drugNamesForRx(prescriptions: Prescription[], rxIndexes: number[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const i of rxIndexes) {
    for (const drug of prescriptions[i]?.drugs ?? []) {
      const key = drug.name.toLowerCase();
      if (!seen.has(key)) { seen.add(key); names.push(drug.name); }
    }
  }
  return names;
}

// Thân đồ thị + view-stack phân cấp đơn→thuốc→hoạt chất, không kèm popup nghiêm
// trọng - dùng chung cho cả trang "Tra cứu tương tác" (qua InteractionResultView,
// có popup riêng) và trang chi tiết lịch sử (check-result, không có popup dismiss được).
export default function InteractionGraphExplorer({ result, prescriptions, audience = "patient" }: InteractionGraphExplorerProps) {
  const boardMode = prescriptions.length > 1;

  const [viewStack, setViewStack] = useState<GraphLevel[]>(() =>
    boardMode ? [{ kind: "prescriptions" }] : [{ kind: "drugs", rxIndexes: [0] }]
  );

  useEffect(() => {
    setViewStack(boardMode ? [{ kind: "prescriptions" }] : [{ kind: "drugs", rxIndexes: [0] }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const origins = useMemo(() => drugOrigins(prescriptions), [prescriptions]);
  const dataExplanations = useMemo(() => withDataOnly(result.explanations), [result]);
  const productEdges = useMemo(() => buildProductGraph(mergedDrugNames(prescriptions), dataExplanations), [prescriptions, dataExplanations]);
  const prescriptionEdges = useMemo(() => (boardMode ? buildPrescriptionGraph(productEdges, origins) : []), [boardMode, productEdges, origins]);

  // Giải thích cấp thuốc/cấp đơn do BACKEND tự sinh riêng (chỉ nhắc tên đúng cấp
  // đó) - tra theo cặp tên thuốc (không phân biệt hoa/thường, không phân biệt thứ
  // tự) hoặc cặp chỉ số đơn. Có thể rỗng với lịch sử cũ lưu trước khi tính năng này
  // tồn tại - khi đó rơi về representativeExplanation (giải thích cấp hoạt chất đại
  // diện) như hành vi cũ để không vỡ trang xem lại.
  const productExplanationByPair = useMemo(() => {
    const map = new Map<string, NonNullable<typeof result.product_explanations>[number]>();
    for (const item of result.product_explanations ?? []) {
      map.set([item.thuoc_a.toLowerCase(), item.thuoc_b.toLowerCase()].sort().join("::"), item);
    }
    return map;
  }, [result]);
  const prescriptionExplanationByPair = useMemo(() => {
    const map = new Map<string, NonNullable<typeof result.prescription_explanations>[number]>();
    for (const item of result.prescription_explanations ?? []) {
      const i = Math.min(item.don_a_index, item.don_b_index);
      const j = Math.max(item.don_a_index, item.don_b_index);
      map.set(`${i}::${j}`, item);
    }
    return map;
  }, [result]);

  const current = viewStack[viewStack.length - 1];

  function pushView(level: GraphLevel) {
    setViewStack((s) => [...s, level]);
  }
  function popView() {
    setViewStack((s) => (s.length > 1 ? s.slice(0, -1) : s));
  }

  let title = "Mối liên hệ giữa các thuốc";
  let nodes: GraphNodeVM[] = [];
  let edges: GraphEdgeVM[] = [];
  let groups: GraphGroup[] = [];
  let pairItems: GraphPairItem[] = [];
  let onEdgeSelect: ((edgeId: string) => void) | undefined;

  if (current.kind === "prescriptions") {
    title = "Tương tác giữa các đơn thuốc";
    nodes = prescriptions.map((p, i) => ({ id: `rx-${i}`, label: p.label, groupId: `rx-${i}` }));
    edges = prescriptionEdges.map((e) => ({
      id: `rx-${e.prescriptionAIndex}::rx-${e.prescriptionBIndex}`,
      sourceId: `rx-${e.prescriptionAIndex}`,
      targetId: `rx-${e.prescriptionBIndex}`,
      muc_do: e.muc_do,
      hasIncompletePair: e.hasIncompletePair,
    }));
    groups = [];
    pairItems = prescriptionEdges.map((e) => {
      const backendItem = prescriptionExplanationByPair.get(`${e.prescriptionAIndex}::${e.prescriptionBIndex}`);
      // Lịch sử cũ (trước khi có prescription_explanations) không có backendItem -
      // rơi về đại diện cấp hoạt chất như hành vi cũ để không vỡ trang xem lại.
      const fallback = backendItem ? undefined : representativeExplanation(e.productEdges[0]?.pairs ?? []);
      return {
        id: `rx-${e.prescriptionAIndex}::rx-${e.prescriptionBIndex}`,
        thuocA: prescriptions[e.prescriptionAIndex]?.label ?? `Đơn thuốc ${e.prescriptionAIndex + 1}`,
        thuocB: prescriptions[e.prescriptionBIndex]?.label ?? `Đơn thuốc ${e.prescriptionBIndex + 1}`,
        severity: e.muc_do,
        description: backendItem ? pickText(backendItem, audience) : fallback?.giai_thich ?? "",
        source: backendItem?.nguon_trich_dan ?? fallback?.nguon_trich_dan ?? "",
        hasIncompletePair: e.hasIncompletePair,
      };
    });
    onEdgeSelect = (edgeId) => {
      const edge = prescriptionEdges.find((e) => `rx-${e.prescriptionAIndex}::rx-${e.prescriptionBIndex}` === edgeId);
      if (edge) pushView({ kind: "drugs", rxIndexes: [edge.prescriptionAIndex, edge.prescriptionBIndex] });
    };
  } else if (current.kind === "drugs") {
    const crossPrescription = current.rxIndexes.length === 2;
    const drugEdges: ProductEdge[] = crossPrescription
      ? drugEdgesBetweenPrescriptions(productEdges, current.rxIndexes[0], current.rxIndexes[1], origins)
      : productEdges;
    title = crossPrescription
      ? `Tương tác thuốc giữa ${prescriptions[current.rxIndexes[0]]?.label ?? ""} và ${prescriptions[current.rxIndexes[1]]?.label ?? ""}`
      : "Tương tác giữa các thuốc";
    const names = drugNamesForRx(prescriptions, current.rxIndexes);
    nodes = names.map((name) => ({ id: name, label: name, groupId: crossPrescription ? groupIdForDrug(name, current.rxIndexes, origins) : name }));
    edges = drugEdges.map((e) => ({ id: `${e.productA}::${e.productB}`, sourceId: e.productA, targetId: e.productB, muc_do: e.muc_do, hasIncompletePair: e.hasIncompletePair }));
    groups = crossPrescription
      ? assignGroupColors(current.rxIndexes.map((i) => ({ id: `rx-${i}`, label: prescriptions[i]?.label ?? `Đơn thuốc ${i + 1}` })))
      : [];
    pairItems = drugEdges.map((e) => {
      const backendItem = productExplanationByPair.get([e.productA.toLowerCase(), e.productB.toLowerCase()].sort().join("::"));
      // Lịch sử cũ (trước khi có product_explanations) không có backendItem - rơi
      // về đại diện cấp hoạt chất như hành vi cũ để không vỡ trang xem lại.
      const fallback = backendItem ? undefined : representativeExplanation(e.pairs);
      return {
        id: `${e.productA}::${e.productB}`,
        thuocA: e.productA,
        thuocB: e.productB,
        severity: e.muc_do,
        description: backendItem ? pickText(backendItem, audience) : fallback?.giai_thich ?? "",
        source: backendItem?.nguon_trich_dan ?? fallback?.nguon_trich_dan ?? "",
        hasIncompletePair: e.hasIncompletePair,
        scientificDescription: backendItem?.mo_ta_dich ?? fallback?.mo_ta_dich,
        management: backendItem?.xu_tri_dich ?? fallback?.xu_tri_dich,
      };
    });
    onEdgeSelect = (edgeId) => {
      const edge = drugEdges.find((e) => `${e.productA}::${e.productB}` === edgeId);
      if (edge) pushView({ kind: "ingredients", drugA: edge.productA, drugB: edge.productB });
    };
  } else {
    const ingredientEdges: IngredientEdge[] = buildIngredientGraph(current.drugA, current.drugB, dataExplanations);
    title = `Tương tác hoạt chất giữa ${current.drugA} và ${current.drugB}`;
    const nodeMap = new Map<string, GraphNodeVM>();
    for (const e of ingredientEdges) {
      if (!nodeMap.has(e.ingredientA)) nodeMap.set(e.ingredientA, { id: e.ingredientA, label: e.ingredientA, groupId: e.drugOfA });
      if (!nodeMap.has(e.ingredientB)) nodeMap.set(e.ingredientB, { id: e.ingredientB, label: e.ingredientB, groupId: e.drugOfB });
    }
    nodes = [...nodeMap.values()];
    edges = ingredientEdges.map((e, index) => ({
      id: `ing-${index}-${e.ingredientA}::${e.ingredientB}`,
      sourceId: e.ingredientA,
      targetId: e.ingredientB,
      muc_do: e.muc_do,
      hasIncompletePair: e.muc_do === "chua_phan_loai",
    }));
    groups = assignGroupColors([{ id: current.drugA, label: current.drugA }, { id: current.drugB, label: current.drugB }]);
    pairItems = ingredientEdges.map((e, index) => ({
      id: `ing-${index}-${e.ingredientA}::${e.ingredientB}`,
      thuocA: e.ingredientA,
      thuocB: e.ingredientB,
      severity: e.muc_do,
      description: pickText(e.pairs[0], audience),
      source: e.pairs[0]?.nguon_trich_dan ?? "",
      management: e.pairs[0]?.xu_tri_dich,
      scientificDescription: e.pairs[0]?.mo_ta_dich,
    }));
    onEdgeSelect = undefined; // cấp đáy - không có "xem chi tiết" tiếp
  }

  return (
    <section className="interaction-result panel">
      <div className="interaction-result__header">
        <div><p className="eyebrow">ĐỒ THỊ TƯƠNG TÁC</p><h2>{title}</h2></div>
        <span className={result.has_severe ? "result-pill result-pill--danger" : result.has_unclassified ? "result-pill result-pill--unknown" : "result-pill"}>
          {result.has_severe ? "Cần lưu ý" : result.has_unclassified ? "Chưa cập nhật" : "An toàn"}
        </span>
      </div>
      {viewStack.length > 1 && (
        <button type="button" className="tt-graph-back" onClick={popView}>
          <MaterialIcon name="arrow_back" size={16} /> Quay lại
        </button>
      )}
      <InteractionGraphView
        key={current.kind === "prescriptions" ? "prescriptions" : current.kind === "drugs" ? `drugs-${current.rxIndexes.join(",")}` : `ingredients-${current.drugA}::${current.drugB}`}
        nodes={nodes} edges={edges} groups={groups} ariaLabel={title}
      />
      <SeverityCountStrip edges={edges} />
      {pairItems.length > 0 && (
        <GraphPairList items={pairItems} onViewDetail={onEdgeSelect} />
      )}
      {pairItems.length === 0 && nodes.length > 0 && (
        <div className="interaction-alert interaction-alert--empty"><MaterialIcon name="info" size={20} /><span>Không tìm thấy tương tác nào trong cơ sở dữ liệu cho lựa chọn hiện tại.</span></div>
      )}
    </section>
  );
}
