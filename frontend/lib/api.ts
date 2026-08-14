const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Severity = "nhe" | "trung_binh" | "nang" | "chua_phan_loai";

export type InteractionExplanation = {
  thuoc_a?: string;
  thuoc_b?: string;
  medication_a_id?: string;
  medication_b_id?: string;
  muc_do?: Severity;
  giai_thich: string;
  // Bản giọng điệu khoa học/chuyên nghiệp dành cho dược sĩ - chỉ có mặt khi gọi qua
  // endpoint/luồng dành cho dược sĩ (giống xu_tri/thay_the/mo_ta bên dưới).
  giai_thich_duoc_si?: string;
  nguon_trich_dan: string;
  // Chỉ có mặt khi gọi qua endpoint dành cho dược sĩ (GET /pharmacist/reviews/{id}).
  xu_tri?: string;
  thay_the_a?: string;
  thay_the_b?: string;
  // Mô tả khoa học nguyên văn từ CSDL DDInter 2.0 (không qua AI diễn giải lại) -
  // cũng chỉ dược sĩ mới thấy, giống xu_tri/thay_the.
  mo_ta?: string;
  // Bản dịch nguyên văn (không qua diễn giải, chỉ dịch sát nghĩa) từ tiếng Anh sang
  // tiếng Việt của mo_ta/xu_tri gốc - cùng mức truy cập, chỉ dược sĩ mới thấy.
  mo_ta_dich?: string;
  xu_tri_dich?: string;
  // Chỉ có ở luồng kiểm tra theo tên thuốc (products/check) - hoạt chất gốc và
  // danh sách tên thuốc (trong lần kiểm tra hiện tại) chứa hoạt chất đó, dùng để
  // gộp (rollup) cạnh ở cấp thuốc trên đồ thị tương tác.
  hoat_chat_a?: string;
  hoat_chat_b?: string;
  san_pham_a?: string[];
  san_pham_b?: string[];
};

// Giải thích cấp thuốc (thuốc-với-thuốc) do backend tự tổng hợp + sinh riêng - chỉ
// nhắc tên 2 thuốc, không lộ tên hoạt chất bên trong (khác InteractionExplanation).
export type ProductLevelExplanation = {
  thuoc_a: string;
  thuoc_b: string;
  muc_do?: Severity;
  giai_thich: string;
  giai_thich_duoc_si?: string;
  nguon_trich_dan: string;
  // Bản dịch nguyên văn (Anh -> Việt) của mo_ta/xu_tri lấy từ cặp hoạt chất góp
  // phần nặng nhất - chỉ dược sĩ mới thấy, giống ProductLevelExplanation khác.
  mo_ta_dich?: string;
  xu_tri_dich?: string;
};

// Giải thích cấp đơn thuốc (đơn-với-đơn) - don_a_index/don_b_index là chỉ số đơn
// theo đúng thứ tự mảng "prescriptions" đã gửi lên trong request.
export type PrescriptionLevelExplanation = {
  don_a: string;
  don_b: string;
  don_a_index: number;
  don_b_index: number;
  muc_do?: Severity;
  giai_thich: string;
  giai_thich_duoc_si?: string;
  nguon_trich_dan: string;
};

// Đoạn tóm tắt tổng quan toàn bộ lần phân tích (cả luồng bệnh nhân và dược sĩ, khác
// giọng điệu) - LLM sinh 1 đoạn dựa trên thống kê + toàn bộ giải thích cấp thuốc-thuốc tìm được.
export type InteractionOverviewExplanation = {
  giai_thich: string;
  so_cap_nang: number;
  so_cap_trung_binh: number;
  so_cap_nhe: number;
  so_cap_chua_phan_loai: number;
  tong_so_cap: number;
};

export type MedicationCheckResponse = {
  interaction_check_id: string;
  ranked_results: Record<string, unknown>[];
  explanations: InteractionExplanation[];
  has_severe: boolean;
  has_unclassified: boolean;
  // Chỉ có ở luồng kiểm tra theo tên thuốc (checkProducts/...).
  unknown_products?: string[];
  no_interaction_data_products?: string[];
  product_explanations?: ProductLevelExplanation[];
  prescription_explanations?: PrescriptionLevelExplanation[];
  overview?: InteractionOverviewExplanation;
  // Ghi chú dược sĩ để lại khi xác nhận lần kiểm tra này - chỉ có ở
  // getPatientCheckDetail khi đã có dược sĩ xác nhận, undefined mọi trường hợp khác.
  ghi_chu_duoc_si?: string;
  ten_duoc_si_xac_nhan?: string;
};

// Kết quả thô từ GET /pharmacist/reviews/{id} - chính là state agent đầy đủ
// (không có interaction_check_id bên trong, có thể thiếu field nếu rỗng).
export type AgentCheckResult = {
  ranked_results?: Record<string, unknown>[];
  explanations?: InteractionExplanation[];
  has_severe?: boolean;
  has_unclassified?: boolean;
  product_explanations?: ProductLevelExplanation[];
  prescription_explanations?: PrescriptionLevelExplanation[];
};

// Payload gửi lên các endpoint /products/check - 1 phần tử = 1 đơn thuốc.
export type PrescriptionCheckInput = { label: string; products: string[] };

export type AuthResponse = {
  access_token: string;
  vai_tro: "patient" | "pharmacist";
  user_id: string;
  ho_ten: string;
};

export type MedicationItem = {
  id: string;
  product_id: string;
  ten_thuoc: string;
  prescription_id: string;
  ngay_bat_dau: string | null;
  ngay_ket_thuc: string | null;
};

// Đơn thuốc đã lưu trong hồ sơ bệnh nhân (tab "Đơn thuốc của tôi") - khác
// `PrescriptionCheckInput`/`Prescription` (lib/prescription.ts) vốn chỉ sống trong
// phiên làm việc của bàn cân tương tác, không có id thật từ backend.
export type PatientPrescription = {
  id: string;
  label: string;
  medications: MedicationItem[];
};

export type MedicationSearchResult = {
  id: string;
  ten_chuan_hoa: string;
};

export type ProductSearchResult = {
  id: string;
  ten_thuoc: string;
};

export type PatientSummary = {
  id: string;
  ho_ten: string;
  co_canh_bao_nang_chua_xu_ly: boolean;
};

export type InteractionCheckSummary = {
  id: string;
  thoi_gian_kiem_tra: string;
  co_canh_bao_nang: boolean;
  co_chua_phan_loai: boolean;
  trang_thai_xac_nhan: string;
};

export type PharmacistReviewResponse = {
  id: string;
  interaction_check_id: string;
  trang_thai_xac_nhan: string;
  ghi_chu: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, headers, ...rest } = options;
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!res.ok) {
    let detail = `Lỗi ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // body không phải JSON hợp lệ - giữ nguyên thông báo mặc định
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Auth ----

export async function register(
  hoTen: string,
  email: string,
  matKhau: string,
  vaiTro: "patient" | "pharmacist"
): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ ho_ten: hoTen, email, mat_khau: matKhau, vai_tro: vaiTro }),
  });
}

export async function login(email: string, matKhau: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, mat_khau: matKhau }),
  });
}

// ---- Tra cứu / hồ sơ thuốc ----

export async function searchMedications(
  q: string,
  token: string
): Promise<MedicationSearchResult[]> {
  return request<MedicationSearchResult[]>(
    `/api/v1/medications/search?q=${encodeURIComponent(q)}`,
    { token }
  );
}

export async function searchGuestMedications(q: string): Promise<MedicationSearchResult[]> {
  return request<MedicationSearchResult[]>(`/api/v1/guest/medications/search?q=${encodeURIComponent(q)}`);
}

export async function searchProducts(q: string, token: string): Promise<ProductSearchResult[]> {
  return request<ProductSearchResult[]>(
    `/api/v1/products/search?q=${encodeURIComponent(q)}`,
    { token }
  );
}

export async function searchGuestProducts(q: string): Promise<ProductSearchResult[]> {
  return request<ProductSearchResult[]>(`/api/v1/guest/products/search?q=${encodeURIComponent(q)}`);
}

export async function listPatientMedications(
  patientId: string,
  token: string
): Promise<MedicationItem[]> {
  return request<MedicationItem[]>(`/api/v1/patients/${patientId}/medications`, { token });
}

export async function addPatientMedication(
  patientId: string,
  productName: string,
  token: string,
  prescriptionId?: string
): Promise<MedicationItem> {
  return request<MedicationItem>(`/api/v1/patients/${patientId}/medications`, {
    method: "POST",
    token,
    body: JSON.stringify({ product_name: productName, prescription_id: prescriptionId }),
  });
}

export async function removePatientMedication(
  patientId: string,
  patientMedicationId: string,
  token: string
): Promise<void> {
  return request<void>(`/api/v1/patients/${patientId}/medications/${patientMedicationId}`, {
    method: "DELETE",
    token,
  });
}

export async function listPatientPrescriptions(
  patientId: string,
  token: string
): Promise<PatientPrescription[]> {
  return request<PatientPrescription[]>(`/api/v1/patients/${patientId}/prescriptions`, { token });
}

export async function createPatientPrescription(
  patientId: string,
  label: string,
  token: string
): Promise<PatientPrescription> {
  return request<PatientPrescription>(`/api/v1/patients/${patientId}/prescriptions`, {
    method: "POST",
    token,
    body: JSON.stringify({ label }),
  });
}

export async function renamePatientPrescription(
  patientId: string,
  prescriptionId: string,
  label: string,
  token: string
): Promise<PatientPrescription> {
  return request<PatientPrescription>(`/api/v1/patients/${patientId}/prescriptions/${prescriptionId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ label }),
  });
}

export async function deletePatientPrescription(
  patientId: string,
  prescriptionId: string,
  token: string
): Promise<void> {
  return request<void>(`/api/v1/patients/${patientId}/prescriptions/${prescriptionId}`, {
    method: "DELETE",
    token,
  });
}

// ---- Kiểm tra tương tác ----

export async function checkMedications(
  medications: string[],
  token: string
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/medications/check", {
    method: "POST",
    token,
    body: JSON.stringify({ medications }),
  });
}

export async function checkGuestMedications(medications: string[]): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/guest/medications/check", {
    method: "POST",
    body: JSON.stringify({ medications }),
  });
}

export async function checkProducts(
  prescriptions: PrescriptionCheckInput[],
  token: string
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/products/check", {
    method: "POST",
    token,
    body: JSON.stringify({ prescriptions }),
  });
}

export async function checkGuestProducts(
  prescriptions: PrescriptionCheckInput[]
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/guest/products/check", {
    method: "POST",
    body: JSON.stringify({ prescriptions }),
  });
}

export async function listPatientChecks(
  patientId: string,
  token: string
): Promise<InteractionCheckSummary[]> {
  return request<InteractionCheckSummary[]>(`/api/v1/patients/${patientId}/checks`, { token });
}

export async function getPatientCheckDetail(
  patientId: string,
  checkId: string,
  token: string
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>(`/api/v1/patients/${patientId}/checks/${checkId}`, {
    token,
  });
}

export async function deleteAllPatientChecks(
  patientId: string,
  token: string
): Promise<void> {
  return request<void>(`/api/v1/patients/${patientId}/checks`, {
    method: "DELETE",
    token,
  });
}

export async function deletePatientCheck(
  patientId: string,
  checkId: string,
  token: string
): Promise<void> {
  return request<void>(`/api/v1/patients/${patientId}/checks/${checkId}`, {
    method: "DELETE",
    token,
  });
}

// ---- Dược sĩ ----

export interface PharmacistSummary {
  id: string;
  ho_ten: string;
  noi_cong_tac?: string;
  mo_ta_ngan?: string;
}

export async function getPharmacists(token: string): Promise<PharmacistSummary[]> {
  return request<PharmacistSummary[]>("/api/v1/pharmacists", { token });
}

// Ngữ cảnh bệnh nhân chọn gửi kèm khi nhờ dược sĩ xác nhận: hồ sơ cá nhân của
// chính mình (guiKemHoSo=true), HOẶC tự nhập thông tin cho trường hợp tra cứu hộ
// người khác (2 field đầu bắt buộc điền chung, ghi chú tùy chọn), HOẶC không gửi gì.
export type RequestReviewPayload = {
  guiKemHoSo?: boolean;
  tenNguoiDuocKiemTra?: string;
  ngaySinhNhapTay?: string;
  ghiChuNhapTay?: string;
};

export async function requestReview(
  checkId: string,
  pharmacistId: string,
  token: string,
  payload?: RequestReviewPayload
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/v1/checks/${checkId}/pharmacists/${pharmacistId}/request_review`, {
    method: "POST",
    token,
    body: JSON.stringify({
      gui_kem_ho_so: payload?.guiKemHoSo ?? false,
      ten_nguoi_duoc_kiem_tra: payload?.tenNguoiDuocKiemTra || null,
      ngay_sinh_nhap_tay: payload?.ngaySinhNhapTay || null,
      ghi_chu_nhap_tay: payload?.ghiChuNhapTay || null,
    }),
  });
}

export interface ReviewRequestSummary {
  check_id: string;
  patient_id: string;
  patient_name: string;
  thoi_gian_kiem_tra: string;
  co_canh_bao_nang: boolean;
  trang_thai_xac_nhan: string;
  gui_kem_ho_so: boolean;
  ten_nguoi_duoc_kiem_tra: string | null;
  ngay_sinh_nhap_tay: string | null;
  ghi_chu_nhap_tay: string | null;
  ghi_chu: string | null;
  thoi_gian_xac_nhan: string | null;
}

export async function listPharmacistRequests(
  token: string
): Promise<ReviewRequestSummary[]> {
  return request<ReviewRequestSummary[]>(`/api/v1/pharmacist/requests`, {
    token,
  });
}

export async function getInteractionCheckDetail(
  checkId: string,
  token: string
): Promise<AgentCheckResult> {
  return request<AgentCheckResult>(`/api/v1/pharmacist/reviews/${checkId}`, { token });
}

export async function submitPharmacistReview(
  checkId: string,
  ghiChu: string,
  token: string
): Promise<PharmacistReviewResponse> {
  return request<PharmacistReviewResponse>("/api/v1/pharmacist/reviews", {
    method: "POST",
    token,
    body: JSON.stringify({ interaction_check_id: checkId, ghi_chu: ghiChu }),
  });
}

export async function checkMedicationsAsPharmacist(
  medications: string[],
  token: string
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/pharmacist/medications/check", {
    method: "POST",
    token,
    body: JSON.stringify({ medications }),
  });
}

export async function checkProductsAsPharmacist(
  prescriptions: PrescriptionCheckInput[],
  token: string
): Promise<MedicationCheckResponse> {
  return request<MedicationCheckResponse>("/api/v1/pharmacist/products/check", {
    method: "POST",
    token,
    body: JSON.stringify({ prescriptions }),
  });
}

// ---- Hồ sơ cá nhân bệnh nhân ----

export type PatientProfileInfo = {
  ho_ten: string | null;
  ngay_sinh: string | null;
  gioi_tinh: string | null;
  can_nang: number | null;
  chieu_cao: number | null;
  benh_nen_ghi_chu: string | null;
  di_ung_thuoc: string | null;
  tinh_trang_khac: string | null;
};

export async function getPatientProfile(
  patientId: string,
  token: string
): Promise<PatientProfileInfo> {
  return request<PatientProfileInfo>(`/api/v1/patients/${patientId}/profile`, { token });
}

export async function updatePatientProfile(
  patientId: string,
  data: Partial<PatientProfileInfo>,
  token: string
): Promise<PatientProfileInfo> {
  return request<PatientProfileInfo>(`/api/v1/patients/${patientId}/profile`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

// ---- Hồ sơ cá nhân dược sĩ ----

export type PharmacistProfileInfo = {
  ho_ten: string | null;
  noi_cong_tac: string | null;
  mo_ta_ngan: string | null;
};

export async function getPharmacistProfile(
  pharmacistId: string,
  token: string
): Promise<PharmacistProfileInfo> {
  return request<PharmacistProfileInfo>(`/api/v1/pharmacists/${pharmacistId}/profile`, { token });
}

export async function updatePharmacistProfile(
  pharmacistId: string,
  data: Partial<PharmacistProfileInfo>,
  token: string
): Promise<PharmacistProfileInfo> {
  return request<PharmacistProfileInfo>(`/api/v1/pharmacists/${pharmacistId}/profile`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

// ---- Thông báo ----

export type NotificationItem = {
  id: string;
  noi_dung: string;
  da_doc: boolean;
  thoi_gian_tao: string;
  interaction_check_id: string | null;
};

export async function listPatientNotifications(
  patientId: string,
  token: string
): Promise<NotificationItem[]> {
  return request<NotificationItem[]>(`/api/v1/patients/${patientId}/notifications`, { token });
}

export async function markNotificationRead(
  patientId: string,
  notificationId: string,
  token: string
): Promise<void> {
  return request<void>(`/api/v1/patients/${patientId}/notifications/${notificationId}/read`, {
    method: "POST",
    token,
  });
}
