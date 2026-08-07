const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Severity = "nhe" | "trung_binh" | "nang" | "chua_phan_loai";

export type InteractionExplanation = {
  thuoc_a?: string;
  thuoc_b?: string;
  medication_a_id?: string;
  medication_b_id?: string;
  muc_do?: Severity;
  giai_thich: string;
  nguon_trich_dan: string;
  // Chỉ có mặt khi gọi qua endpoint dành cho dược sĩ (GET /pharmacist/reviews/{id}).
  xu_tri?: string;
  thay_the_a?: string;
  thay_the_b?: string;
};

export type MedicationCheckResponse = {
  interaction_check_id: string;
  ranked_results: Record<string, unknown>[];
  explanations: InteractionExplanation[];
  has_severe: boolean;
  has_unclassified: boolean;
  // Ghi chú của dược sĩ nếu lần kiểm tra này đã được xác nhận, ngược lại null.
  ghi_chu: string | null;
};

// Kết quả thô từ GET /pharmacist/reviews/{id} - chính là state agent đầy đủ
// (không có interaction_check_id bên trong, có thể thiếu field nếu rỗng), cộng
// thêm ghi_chu/trang_thai_xac_nhan của CHÍNH dược sĩ đang xem (nếu đã xác nhận).
export type AgentCheckResult = {
  ranked_results?: Record<string, unknown>[];
  explanations?: InteractionExplanation[];
  has_severe?: boolean;
  has_unclassified?: boolean;
  ghi_chu?: string | null;
  trang_thai_xac_nhan?: string;
};

export type AuthResponse = {
  access_token: string;
  vai_tro: "patient" | "pharmacist";
  user_id: string;
  ho_ten: string;
};

export type MedicationItem = {
  id: string;
  medication_id: string;
  ten_chuan_hoa: string;
  ngay_bat_dau: string | null;
  ngay_ket_thuc: string | null;
};

export type MedicationSearchResult = {
  id: string;
  ten_chuan_hoa: string;
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

export async function listPatientMedications(
  patientId: string,
  token: string
): Promise<MedicationItem[]> {
  return request<MedicationItem[]>(`/api/v1/patients/${patientId}/medications`, { token });
}

export async function addPatientMedication(
  patientId: string,
  medicationName: string,
  token: string
): Promise<MedicationItem> {
  return request<MedicationItem>(`/api/v1/patients/${patientId}/medications`, {
    method: "POST",
    token,
    body: JSON.stringify({ medication_name: medicationName }),
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

// ---- Dược sĩ ----

export async function listPharmacistPatients(
  pharmacistId: string,
  token: string
): Promise<PatientSummary[]> {
  return request<PatientSummary[]>(`/api/v1/pharmacist/${pharmacistId}/patients`, { token });
}

export async function listPatientChecksForPharmacist(
  patientId: string,
  token: string
): Promise<InteractionCheckSummary[]> {
  return request<InteractionCheckSummary[]>(`/api/v1/pharmacist/patients/${patientId}/checks`, {
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
