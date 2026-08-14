import type { PrescriptionCheckInput } from "@/lib/api";

export type SelectedDrug = { name: string; known: boolean };

export type Prescription = { id: string; label: string; drugs: SelectedDrug[] };

export function createPrescription(index: number): Prescription {
  return { id: `rx-${Date.now()}-${index}`, label: `Đơn thuốc ${index}`, drugs: [] };
}

// Bỏ các đơn rỗng rồi quy đổi sang payload gửi lên /products/check - đơn thuốc rỗng
// không có ý nghĩa để backend tính cạnh cấp đơn, và schema yêu cầu mỗi đơn có ít
// nhất 1 thuốc. Dùng CHÍNH danh sách đã lọc này (không phải `prescriptions` gốc) để
// dựng đồ thị phía frontend, để chỉ số đơn khớp với don_a_index/don_b_index backend trả về.
export function nonEmptyPrescriptions(prescriptions: Prescription[]): Prescription[] {
  return prescriptions.filter((p) => p.drugs.length > 0);
}

export function toPrescriptionCheckInput(prescriptions: Prescription[]): PrescriptionCheckInput[] {
  return nonEmptyPrescriptions(prescriptions).map((p) => ({
    label: p.label,
    products: p.drugs.map((d) => d.name),
  }));
}

// Danh sách tên thuốc duy nhất (không phân biệt hoa thường), gộp từ mọi đơn thuốc, theo thứ tự xuất hiện.
export function mergedDrugNames(prescriptions: Prescription[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const prescription of prescriptions) {
    for (const drug of prescription.drugs) {
      const key = drug.name.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        names.push(drug.name);
      }
    }
  }
  return names;
}

// Với mỗi tên thuốc (chữ thường), tập chỉ số các đơn thuốc có chứa thuốc đó.
export function drugOrigins(prescriptions: Prescription[]): Map<string, Set<number>> {
  const origins = new Map<string, Set<number>>();
  prescriptions.forEach((prescription, index) => {
    for (const drug of prescription.drugs) {
      const key = drug.name.toLowerCase();
      if (!origins.has(key)) origins.set(key, new Set());
      origins.get(key)!.add(index);
    }
  });
  return origins;
}

// Một cặp tương tác được coi là "giữa các đơn" trừ khi cả hai thuốc chỉ xuất hiện, và cùng xuất hiện, trong đúng 1 đơn thuốc.
export function isCrossPrescription(origins: Map<string, Set<number>>, nameA?: string, nameB?: string): boolean {
  if (!nameA || !nameB) return false;
  const setA = origins.get(nameA.toLowerCase());
  const setB = origins.get(nameB.toLowerCase());
  if (!setA || !setB || setA.size === 0 || setB.size === 0) return false;
  if (setA.size === 1 && setB.size === 1 && [...setA][0] === [...setB][0]) return false;
  return true;
}

// Nhãn hiển thị nguồn gốc đơn thuốc cho 1 cặp tương tác, ví dụ "Đơn thuốc 1 × Đơn thuốc 2" hoặc "Trong Đơn thuốc 1".
export function originLabel(prescriptions: Prescription[], origins: Map<string, Set<number>>, nameA?: string, nameB?: string): string | null {
  if (!nameA || !nameB) return null;
  const setA = origins.get(nameA.toLowerCase());
  const setB = origins.get(nameB.toLowerCase());
  if (!setA || !setB) return null;
  const combined = [...new Set([...setA, ...setB])].sort((a, b) => a - b);
  if (combined.length === 0) return null;
  const labels = combined.map((index) => prescriptions[index]?.label ?? `Đơn thuốc ${index + 1}`);
  return combined.length === 1 ? `Trong ${labels[0]}` : labels.join(" × ");
}
