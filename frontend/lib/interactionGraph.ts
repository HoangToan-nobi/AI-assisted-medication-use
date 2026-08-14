import type { InteractionExplanation, Severity } from "@/lib/api";

// Cạnh giữa 2 THUỐC = mức độ nghiêm trọng cao nhất trong các cặp HOẠT CHẤT của
// 2 thuốc đó (rollup). "pairs" giữ lại toàn bộ cặp hoạt chất góp phần vào cạnh
// này, sắp xếp nặng nhất trước, để hiển thị khi bấm xem chi tiết.
export type ProductEdge = {
  productA: string;
  productB: string;
  muc_do?: Severity;
  // true nếu còn ít nhất 1 cặp hoạt chất chưa có dữ liệu/chưa phân loại, dù cạnh
  // đã có màu theo mức nặng nhất đã biết - tránh chủ quan khi rollup che khuất nó.
  hasIncompletePair: boolean;
  pairs: InteractionExplanation[];
};

// Cạnh giữa 2 ĐƠN THUỐC = mức độ nghiêm trọng cao nhất trong các cạnh cấp-thuốc
// giữa 2 đơn đó. "productEdges" giữ toàn bộ cạnh thuốc góp phần, nặng nhất trước.
export type PrescriptionEdge = {
  prescriptionAIndex: number;
  prescriptionBIndex: number;
  muc_do?: Severity;
  hasIncompletePair: boolean;
  productEdges: ProductEdge[];
};

// Cạnh giữa 2 HOẠT CHẤT thuộc đúng 2 thuốc đang xem chi tiết (cấp đáy, không rollup thêm).
export type IngredientEdge = {
  ingredientA: string;
  ingredientB: string;
  drugOfA: string;
  drugOfB: string;
  muc_do?: Severity;
  pairs: InteractionExplanation[];
};

export type GraphGroup = { id: string; label: string; color: string };

// Bảng màu nền node cố định, chủ ý khác biệt hoàn toàn với 4 màu severity dùng cho
// cạnh (đỏ #c94740 / hổ phách #c58a32 / xanh lá #5d9b78 / xám #8d98a4), để không
// nhầm lẫn "màu nhóm" với "màu mức độ tương tác" khi cả hai cùng xuất hiện trên đồ thị.
export const NODE_FILL_PALETTE = ["#4f7cc9", "#8b5fbf", "#2f9e8f", "#c9578a", "#5b5fc7", "#b8763f"];

const SEVERITY_RANK: Record<string, number> = { nang: 3, trung_binh: 2, nhe: 1, chua_phan_loai: 0 };

function severityRank(muc_do?: Severity): number {
  return muc_do ? (SEVERITY_RANK[muc_do] ?? -1) : -1;
}

function edgeKey(a: string, b: string): string {
  return [a.toLowerCase(), b.toLowerCase()].sort().join("::");
}

// Dựng lại danh sách tên thuốc duy nhất từ 1 lần tra cứu ĐÃ LƯU (lịch sử) - nơi
// không còn giữ thông tin đơn thuốc gốc, chỉ có san_pham_a/b (hoặc thuoc_a/b dự
// phòng) trong từng cặp giải thích. Dùng để dựng 1 "đơn thuốc" tổng hợp duy nhất
// khi xem lại chi tiết ở trang lịch sử.
export function productNamesFromExplanations(explanations: InteractionExplanation[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const exp of explanations) {
    const prods = [
      ...(exp.san_pham_a?.length ? exp.san_pham_a : exp.thuoc_a ? [exp.thuoc_a] : []),
      ...(exp.san_pham_b?.length ? exp.san_pham_b : exp.thuoc_b ? [exp.thuoc_b] : []),
    ];
    for (const p of prods) {
      const key = p.toLowerCase();
      if (!seen.has(key)) { seen.add(key); names.push(p); }
    }
  }
  return names;
}

// Loại hẳn các cặp KHÔNG CÓ DỮ LIỆU trong CSDL tương tác (không vẽ, không nhắc tới).
// Khác với "chua_phan_loai" (có dữ liệu, chỉ là chưa rõ mức độ) - cặp đó vẫn giữ lại,
// nhận biết bằng việc backend luôn set muc_do="chua_phan_loai" tường minh cho nó,
// trong khi cặp không có dữ liệu hoàn toàn không có field muc_do.
export function withDataOnly(explanations: InteractionExplanation[]): InteractionExplanation[] {
  return explanations.filter((e) => e.muc_do !== undefined);
}

// products: tên thuốc đang chọn trên UI (thứ tự hiển thị node).
// explanations: danh sách cặp hoạt chất trả về từ API (đã enrich san_pham_a/b ở backend).
export function buildProductGraph(products: string[], explanations: InteractionExplanation[]): ProductEdge[] {
  const edges = new Map<string, ProductEdge>();

  for (const exp of explanations) {
    const prodsA = exp.san_pham_a?.length ? exp.san_pham_a : exp.thuoc_a ? [exp.thuoc_a] : [];
    const prodsB = exp.san_pham_b?.length ? exp.san_pham_b : exp.thuoc_b ? [exp.thuoc_b] : [];
    const incomplete = !exp.muc_do || exp.muc_do === "chua_phan_loai";

    for (const productA of prodsA) {
      for (const productB of prodsB) {
        if (productA.toLowerCase() === productB.toLowerCase()) continue; // cùng 1 thuốc phối hợp - không tính là cạnh
        const key = edgeKey(productA, productB);
        const existing = edges.get(key);
        if (!existing) {
          edges.set(key, { productA, productB, muc_do: exp.muc_do, hasIncompletePair: incomplete, pairs: [exp] });
          continue;
        }
        existing.pairs.push(exp);
        existing.hasIncompletePair = existing.hasIncompletePair || incomplete;
        if (severityRank(exp.muc_do) > severityRank(existing.muc_do)) existing.muc_do = exp.muc_do;
      }
    }
  }

  for (const edge of edges.values()) edge.pairs.sort((a, b) => severityRank(b.muc_do) - severityRank(a.muc_do));

  // Giữ thứ tự node ổn định theo danh sách products đầu vào cho cả 2 đầu cạnh.
  const order = new Map(products.map((name, index) => [name.toLowerCase(), index]));
  return [...edges.values()].sort((a, b) => (order.get(a.productA.toLowerCase()) ?? 0) - (order.get(b.productA.toLowerCase()) ?? 0));
}

// Gộp ProductEdge[] (đã tính trên toàn bộ danh sách thuốc gộp từ mọi đơn) lên cấp
// đơn thuốc. Với mỗi cạnh thuốc, xét MỌI cặp chỉ số đơn (rxA, rxB) mà 2 đầu cạnh
// thuộc về - vì origins không đảm bảo mỗi thuốc chỉ thuộc đúng 1 đơn.
export function buildPrescriptionGraph(productEdges: ProductEdge[], origins: Map<string, Set<number>>): PrescriptionEdge[] {
  const edges = new Map<string, PrescriptionEdge>();

  for (const pe of productEdges) {
    const setA = origins.get(pe.productA.toLowerCase());
    const setB = origins.get(pe.productB.toLowerCase());
    if (!setA || !setB) continue;
    for (const rxA of setA) {
      for (const rxB of setB) {
        if (rxA === rxB) continue; // bỏ qua tương tác trong cùng 1 đơn
        const i = Math.min(rxA, rxB);
        const j = Math.max(rxA, rxB);
        const key = `${i}::${j}`;
        const existing = edges.get(key);
        if (!existing) {
          edges.set(key, { prescriptionAIndex: i, prescriptionBIndex: j, muc_do: pe.muc_do, hasIncompletePair: pe.hasIncompletePair, productEdges: [pe] });
          continue;
        }
        if (!existing.productEdges.includes(pe)) existing.productEdges.push(pe);
        existing.hasIncompletePair = existing.hasIncompletePair || pe.hasIncompletePair;
        if (severityRank(pe.muc_do) > severityRank(existing.muc_do)) existing.muc_do = pe.muc_do;
      }
    }
  }

  for (const edge of edges.values()) edge.productEdges.sort((a, b) => severityRank(b.muc_do) - severityRank(a.muc_do));
  return [...edges.values()].sort((a, b) => a.prescriptionAIndex - b.prescriptionAIndex || a.prescriptionBIndex - b.prescriptionBIndex);
}

// Lọc ProductEdge[] toàn cục, chỉ giữ cạnh thuốc nằm GIỮA đúng 2 đơn đang xem chi
// tiết (rxAIndex, rxBIndex). Kiểm tra cả 2 chiều vì productA/productB không đảm
// bảo thứ tự theo đơn thuốc.
export function drugEdgesBetweenPrescriptions(
  productEdges: ProductEdge[],
  rxAIndex: number,
  rxBIndex: number,
  origins: Map<string, Set<number>>
): ProductEdge[] {
  return productEdges.filter((pe) => {
    const setA = origins.get(pe.productA.toLowerCase());
    const setB = origins.get(pe.productB.toLowerCase());
    if (!setA || !setB) return false;
    return (setA.has(rxAIndex) && setB.has(rxBIndex)) || (setA.has(rxBIndex) && setB.has(rxAIndex));
  });
}

// Cấp đáy: rescan trực tiếp explanations gốc cho đúng 2 thuốc drugA/drugB đang xem
// chi tiết (KHÔNG dùng ProductEdge.pairs, vì san_pham_a/b của các exp gộp vào 1
// cạnh thuốc không đảm bảo cùng chiều). Kiểm tra cả 2 chiều để gán đúng
// ingredientA/B - drugOfA/B.
export function buildIngredientGraph(drugA: string, drugB: string, explanations: InteractionExplanation[]): IngredientEdge[] {
  const drugALower = drugA.toLowerCase();
  const drugBLower = drugB.toLowerCase();
  const edges: IngredientEdge[] = [];

  for (const exp of explanations) {
    const prodsA = exp.san_pham_a?.length ? exp.san_pham_a : exp.thuoc_a ? [exp.thuoc_a] : [];
    const prodsB = exp.san_pham_b?.length ? exp.san_pham_b : exp.thuoc_b ? [exp.thuoc_b] : [];
    const aHasDrugA = prodsA.some((p) => p.toLowerCase() === drugALower);
    const aHasDrugB = prodsA.some((p) => p.toLowerCase() === drugBLower);
    const bHasDrugA = prodsB.some((p) => p.toLowerCase() === drugALower);
    const bHasDrugB = prodsB.some((p) => p.toLowerCase() === drugBLower);

    let drugOfA: string | undefined;
    let drugOfB: string | undefined;
    if (aHasDrugA && bHasDrugB) { drugOfA = drugA; drugOfB = drugB; }
    else if (aHasDrugB && bHasDrugA) { drugOfA = drugB; drugOfB = drugA; }
    else continue;

    const ingredientA = exp.hoat_chat_a ?? exp.thuoc_a;
    const ingredientB = exp.hoat_chat_b ?? exp.thuoc_b;
    if (!ingredientA || !ingredientB) continue;
    if (ingredientA.toLowerCase() === ingredientB.toLowerCase()) continue;

    edges.push({ ingredientA, ingredientB, drugOfA, drugOfB, muc_do: exp.muc_do, pairs: [exp] });
  }

  return edges.sort((a, b) => severityRank(b.muc_do) - severityRank(a.muc_do));
}

// Lấy giải thích đại diện (nặng nhất, do pairs đã được các hàm build*Graph sort
// giảm dần theo severity) để hiển thị làm nội dung thẻ AlertCard ở cấp rollup.
export function representativeExplanation(pairs: InteractionExplanation[]): InteractionExplanation | undefined {
  return pairs[0];
}

// Gán màu nền cố định cho từng nhóm theo palette, giữ nguyên nhãn truyền vào. Khi
// chỉ có 0-1 nhóm (không cần phân biệt màu, ví dụ chỉ 1 đơn thuốc), trả về mảng
// rỗng để caller ẩn hẳn phần chú thích màu.
export function assignGroupColors(groups: { id: string; label: string }[]): GraphGroup[] {
  if (groups.length <= 1) return [];
  return groups.map((g, index) => ({ ...g, color: NODE_FILL_PALETTE[index % NODE_FILL_PALETTE.length] }));
}

// Vị trí node trên vòng tròn bán kính r quanh tâm (cx, cy), viewBox 0..100.
export function circleLayout(count: number, cx = 50, cy = 50, r = 38): [number, number][] {
  if (count <= 1) return [[cx, cy]];
  return Array.from({ length: count }, (_, index) => {
    const angle = (2 * Math.PI * index) / count - Math.PI / 2;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  });
}
