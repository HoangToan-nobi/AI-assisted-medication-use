# GIAI ĐOẠN 2: LẬP KẾ HOẠCH & TÀI LIỆU YÊU CẦU
## Đề tài VMEC-12 — MedGuard AI (MVP Final)

**Phạm vi đã chốt:** MVP Final, 2 vai trò (Bệnh nhân + Dược sĩ/Bác sĩ), OCR để ở giai đoạn nâng cao (sau MVP cơ bản).

---

## 1. BRD (Business Requirement Document)

### 1.1 Mục tiêu kinh doanh
Xây dựng một ứng dụng AI Agent giúp bệnh nhân và dược sĩ/bác sĩ kiểm tra an toàn khi dùng nhiều loại thuốc cùng lúc, giảm rủi ro tương tác thuốc nguy hiểm, tăng niềm tin của người dùng vào việc tự quản lý sức khỏe, đồng thời hỗ trợ dược sĩ tư vấn nhanh và chính xác hơn.

### 1.2 Phạm vi dự án (Scope)
**Trong phạm vi (In-scope):**
- Quản lý danh sách thuốc đang dùng theo hồ sơ từng bệnh nhân.
- Tra cứu và cảnh báo tương tác thuốc–thuốc, thuốc–thực phẩm.
- Xếp hạng mức độ nghiêm trọng, giải thích có trích nguồn.
- Cơ chế xác nhận của dược sĩ (Human-in-the-loop).
- Hai vai trò đăng nhập: Bệnh nhân, Dược sĩ/Bác sĩ.

**Ngoài phạm vi (Out-of-scope ở bản MVP Final):**
- OCR quét đơn thuốc từ ảnh (để ở bản nâng cao kế tiếp).
- Tương tác thuốc–bệnh nền (chronic condition) chi tiết — có thể để bản mở rộng.
- Chẩn đoán, kê đơn tự động (KHÔNG bao giờ nằm trong phạm vi vì lý do an toàn y tế).

### 1.3 Các bên liên quan (Stakeholders)
| Vai trò | Trách nhiệm |
|---|---|
| Bệnh nhân | Nhập/theo dõi danh sách thuốc, nhận cảnh báo |
| Dược sĩ / Bác sĩ | Xác nhận cảnh báo, ghi chú, duyệt trường hợp nghiêm trọng |
| Nhóm phát triển | Xây dựng, kiểm thử, triển khai hệ thống |
| Giảng viên/khách hàng đánh giá | Nghiệm thu sản phẩm theo tiêu chí đề tài |

### 1.4 Ràng buộc bắt buộc (Constraints — không được vi phạm)
- **HITL bắt buộc:** mọi cảnh báo là đề xuất tham khảo; quyết định đổi/ngưng thuốc do dược sĩ/bác sĩ quyết định.
- AI **không được** tự chẩn đoán hay tự khuyến nghị đổi thuốc.
- Toàn bộ câu trả lời phải **grounded** (có nguồn) trên CSDL tương tác thuốc mô phỏng — chống bịa đặt (hallucination).
- Tương tác mức **nghiêm trọng** → cảnh báo nổi bật, khuyến cáo liên hệ y tế ngay.
- Bảo mật dữ liệu cá nhân/y tế (PII/PHI).
- Luôn nêu rõ giới hạn dữ liệu khi thuốc không có trong CSDL.

---

## 2. SRS (Software Requirement Specification)

### 2.1 Yêu cầu chức năng (Functional Requirements)

| Mã | Yêu cầu | Vai trò |
|---|---|---|
| FR-01 | Đăng ký/đăng nhập theo 2 vai trò (bệnh nhân, dược sĩ) | Cả hai |
| FR-02 | Thêm/sửa/xóa thuốc trong danh sách đang dùng | Bệnh nhân |
| FR-03 | Agent chuẩn hóa tên thuốc (kể cả viết tắt, biệt dược) | Hệ thống |
| FR-04 | Agent tra cứu tương tác thuốc–thuốc, thuốc–thực phẩm qua RAG trên CSDL | Hệ thống |
| FR-05 | Agent xếp hạng mức độ nghiêm trọng (nhẹ/trung bình/nặng) | Hệ thống |
| FR-06 | Hiển thị giải thích tương tác dễ hiểu kèm trích dẫn nguồn | Bệnh nhân/Dược sĩ |
| FR-07 | Cảnh báo nổi bật + khuyến cáo liên hệ y tế khi mức nghiêm trọng | Hệ thống |
| FR-08 | Dược sĩ xem danh sách bệnh nhân, xác nhận/ghi chú vào cảnh báo | Dược sĩ |
| FR-09 | Lưu lịch sử tra cứu và hồ sơ thuốc theo từng bệnh nhân (memory) | Hệ thống |
| FR-10 | Cảnh báo khi thuốc không có trong CSDL (nêu rõ giới hạn dữ liệu) | Hệ thống |

### 2.2 Yêu cầu phi chức năng (Non-functional Requirements)

| Mã | Yêu cầu |
|---|---|
| NFR-01 | Thời gian phản hồi tra cứu tương tác < 5 giây/lượt |
| NFR-02 | Bảo mật: mã hóa dữ liệu người dùng (PII/PHI), phân quyền rõ theo vai trò |
| NFR-03 | Guardrails: chặn agent đưa ra lời khuyên đổi/kê thuốc |
| NFR-04 | Khả năng mở rộng: kiến trúc cho phép bổ sung OCR, thêm ngôn ngữ ở bản sau |
| NFR-05 | Giao diện thân thiện, dễ dùng với người lớn tuổi (font lớn, rõ ràng) |
| NFR-06 | Hệ thống deploy ổn định trên cloud, uptime ≥ 99% trong thời gian demo/vận hành |

### 2.3 Kiến trúc luồng agent (tóm tắt)
```
Người dùng nhập danh sách thuốc
   → [Node 1: Chuẩn hóa tên thuốc]
   → [Node 2: Tra cứu tương tác (RAG + vector DB)]
   → [Node 3: Xếp hạng mức độ nghiêm trọng]
   → [Node 4: Sinh giải thích có trích nguồn]
   → [Guardrail: chặn khuyên đổi thuốc, buộc citation]
   → Cảnh báo hiển thị cho Bệnh nhân + Dược sĩ (nếu nghiêm trọng → escalate)
```

---

## 3. Product Roadmap

| Giai đoạn | Nội dung | Thời lượng gợi ý |
|---|---|---|
| Sprint 0 | Clone template `P-005`, chạy `scripts/setup_hooks.sh`, bật `chromadb`/`sqlalchemy` trong `requirements.txt`, chuẩn bị CSDL thuốc mô phỏng | 1 tuần |
| Sprint 1 | Xây luồng agent cơ bản: chuẩn hóa → tra cứu → xếp hạng → giải thích | 2 tuần |
| Sprint 2 | Xây frontend 2 vai trò (bệnh nhân/dược sĩ), backend API, tích hợp | 2 tuần |
| Sprint 3 | Guardrails, HITL cho dược sĩ, cảnh báo nghiêm trọng, kiểm thử | 1.5 tuần |
| Sprint 4 (Nâng cao) | OCR quét đơn thuốc, tương tác thuốc–bệnh nền, đa ngôn ngữ | 2 tuần |
| Sprint 5 | QA toàn diện, tối ưu hiệu năng, chuẩn bị demo & trình bày khách hàng | 1 tuần |

---

## 4. User Story & Acceptance Criteria

### US-01: *Là một bệnh nhân*, tôi muốn nhập danh sách thuốc đang dùng để biết có tương tác nguy hiểm hay không, *để* tôi yên tâm khi dùng thuốc.
**Acceptance Criteria:**
- Given tôi đã đăng nhập với vai trò bệnh nhân, When tôi nhập tên thuốc (kể cả viết tắt), Then hệ thống chuẩn hóa được tên thuốc đúng ≥ 90% trường hợp phổ biến.
- Given danh sách thuốc đã nhập ≥ 2 loại, When tôi bấm "Kiểm tra", Then hệ thống trả kết quả tương tác trong < 5 giây.
- Given thuốc không có trong CSDL, When hệ thống không tìm thấy dữ liệu, Then phải hiển thị rõ "không đủ dữ liệu" thay vì im lặng hoặc suy đoán.

### US-02: *Là một bệnh nhân*, tôi muốn nhận cảnh báo rõ ràng kèm giải thích dễ hiểu, *để* tôi biết cần làm gì tiếp theo.
**Acceptance Criteria:**
- Mỗi cảnh báo phải có: mức độ (nhẹ/trung bình/nặng), giải thích ngôn ngữ tự nhiên, và nguồn trích dẫn.
- Mức "nặng" phải hiển thị nổi bật (màu/icon riêng) kèm khuyến cáo liên hệ y tế ngay.

### US-03: *Là một dược sĩ*, tôi muốn xem danh sách cảnh báo của từng bệnh nhân và xác nhận/ghi chú, *để* tôi kiểm soát chất lượng tư vấn.
**Acceptance Criteria:**
- Dược sĩ xem được danh sách bệnh nhân được gán cho mình và lịch sử cảnh báo của từng người.
- Dược sĩ có thể thêm ghi chú và đánh dấu "đã xác nhận" cho từng cảnh báo, ghi chú được lưu vào hồ sơ.

### US-04: *Là một dược sĩ*, tôi muốn được thông báo ngay khi có tương tác mức nghiêm trọng, *để* tôi can thiệp kịp thời.
**Acceptance Criteria:**
- Cảnh báo mức "nặng" phải escalate (đẩy thông báo ưu tiên) tới dược sĩ phụ trách trong < 1 phút kể từ khi phát hiện.

### US-05: *Là hệ thống*, khi thuốc không có trong CSDL, tôi phải thông báo rõ giới hạn dữ liệu thay vì suy đoán, *để* tránh gây hiểu lầm nguy hiểm.
**Acceptance Criteria:**
- Không có trường hợp nào hệ thống trả lời về tương tác của một thuốc ngoài CSDL mà không kèm cảnh báo giới hạn dữ liệu.

---

## 5. Data Model / ERD sơ bộ

**Các bảng chính:**
- `users` (id, ho_ten, vai_tro [patient/pharmacist], email, mat_khau_hash, ngay_tao)
- `patient_profiles` (id, user_id FK, ngay_sinh, benh_nen_ghi_chu)
- `pharmacist_assignments` (id, pharmacist_id FK, patient_id FK)
- `medications` (id, ten_chuan_hoa, ten_biet_duoc, hoat_chat, nguon_du_lieu)
- `patient_medications` (id, patient_id FK, medication_id FK, ngay_bat_dau, ngay_ket_thuc)
- `interactions` (id, medication_a_id FK, medication_b_id FK, muc_do [nhe/trung_binh/nang], mo_ta, nguon_trich_dan)
- `interaction_checks` (id, patient_id FK, ket_qua_json, thoi_gian_kiem_tra)
- `pharmacist_reviews` (id, interaction_check_id FK, pharmacist_id FK, ghi_chu, trang_thai_xac_nhan)

**Quan hệ chính:** 1 bệnh nhân — nhiều thuốc (many-to-many qua `patient_medications`); 1 dược sĩ — nhiều bệnh nhân (qua `pharmacist_assignments`); mỗi lần kiểm tra tương tác (`interaction_checks`) có thể có 1 bản ghi xác nhận của dược sĩ (`pharmacist_reviews`).

> ⚠️ **Ghi chú khớp code thật:** repo hiện tại **chưa có** thư mục ORM models riêng — `src/models/` hiện chỉ chứa `schemas.py` (Pydantic, dùng cho validate request/response, không phải ORM). Cần tạo mới `src/db/` (theo đúng gợi ý cấu trúc trong `README.md` mẫu) chứa `models.py` (SQLAlchemy models cho 8 bảng trên) và `session.py`. `database_url` đã có sẵn trong `config.py`, mặc định SQLite (`sqlite:///./data/app.db`) — dùng nguyên cho dev, không cần đổi sang Postgres cho tới khi deploy production.

---

## 6. API Specification sơ bộ

> ⚠️ **Đã cập nhật khớp với code thật** (xem Giai đoạn 4, mục 7): repo dùng prefix `/api/v1` cho mọi route nghiệp vụ, đã có sẵn `/chat` và `/status` mẫu trong `src/api/routes.py`, và `/health` ở root (`src/main.py`). Bảng dưới đây là bản đã chỉnh cho khớp.

| Method | Endpoint | Mô tả | Trạng thái |
|---|---|---|---|
| GET | `/health` | Health check | ✅ có sẵn trong template |
| POST | `/api/v1/chat` | Gọi agent trực tiếp (dùng để test nhanh khi dev) | ✅ có sẵn trong template |
| GET | `/api/v1/status` | Kiểm tra trạng thái agent | ✅ có sẵn trong template |
| POST | `/api/v1/auth/login` | Đăng nhập theo vai trò | 🆕 cần thêm |
| GET/POST | `/api/v1/patients/{id}/medications` | Xem/thêm thuốc của bệnh nhân | 🆕 cần thêm |
| POST | `/api/v1/medications/check` | Gửi danh sách thuốc, chạy `agent.ainvoke()` với `MedCheckState`, trả kết quả tương tác | 🆕 cần thêm (chi tiết ở GĐ4 mục 7) |
| GET | `/api/v1/pharmacist/{id}/patients` | Dược sĩ xem danh sách bệnh nhân phụ trách | 🆕 cần thêm |
| POST | `/api/v1/pharmacist/reviews` | Dược sĩ xác nhận/ghi chú vào 1 kết quả kiểm tra | 🆕 cần thêm (chi tiết ở GĐ4 mục 7) |
| GET | `/api/v1/medications/search?q=` | Tra cứu/chuẩn hóa tên thuốc | 🆕 cần thêm |

Toàn bộ route "🆕 cần thêm" sẽ được viết vào `src/api/routes.py` cạnh route mẫu, dùng chung `router` đã có (không tạo router mới), và schema tương ứng thêm vào `src/models/schemas.py`.

---

## 7. Ma trận truy vết yêu cầu (Requirement Traceability Matrix — rút gọn)

| FR | User Story liên quan | Test Case (sẽ chi tiết ở giai đoạn QA) |
|---|---|---|
| FR-03, FR-04, FR-05 | US-01 | TC kiểm tra chuẩn hóa tên + tra cứu + xếp hạng đúng |
| FR-06, FR-07 | US-02 | TC kiểm tra hiển thị giải thích + cảnh báo nổi bật |
| FR-08 | US-03, US-04 | TC dược sĩ xác nhận, escalate cảnh báo nặng |
| FR-10 | US-05 | TC thuốc ngoài CSDL trả về đúng cảnh báo giới hạn |

---

## 8. Đánh giá rủi ro (Risk Assessment)

| Rủi ro | Mức độ | Giải pháp giảm thiểu |
|---|---|---|
| CSDL tương tác mô phỏng không đầy đủ/thiếu chính xác | Cao | Luôn nêu rõ giới hạn dữ liệu; không suy đoán ngoài CSDL |
| Agent "ảo giác" (bịa thông tin tương tác) | Cao | Bắt buộc RAG grounded + guardrail chặn câu trả lời không có nguồn |
| Team chỉ 2 người, khối lượng công việc lớn (2 vai trò + agent + OCR nâng cao) | Trung bình | Ưu tiên MVP cơ bản trước, OCR đẩy sang sprint nâng cao như đã chốt |
| Người dùng hiểu nhầm là tư vấn y khoa chính thức | Cao | Disclaimer bắt buộc ở mọi cảnh báo, không cho phép ngôn ngữ mang tính "chỉ định" |
| Trễ tiến độ do tích hợp nhiều thành phần (LLM, RAG, guardrails, 2 frontend) | Trung bình | Bám sát roadmap sprint, kiểm thử sớm từng phần thay vì dồn cuối |

---

## 9. Giả định (Assumptions)
- CSDL tương tác thuốc dùng trong dự án là dữ liệu **mô phỏng**, có cấu trúc tương tự DrugBank/RxNorm, không phải dữ liệu lâm sàng đã được cơ quan y tế kiểm chứng.
- Người dùng thử nghiệm (bệnh nhân/dược sĩ) trong giai đoạn demo là dữ liệu giả lập, không phải bệnh nhân thật.
- Nhóm phát triển có quyền truy cập hạ tầng cloud để deploy trong suốt thời gian dự án.

---

## 10. Định nghĩa hoàn thành cho MVP Final (Definition of Done)
Sản phẩm được coi là hoàn thành MVP Final khi:
- [ ] Toàn bộ FR-01 đến FR-10 hoạt động đúng như Acceptance Criteria.
- [ ] Guardrails chặn được 100% các câu trả lời không có trích dẫn nguồn (kiểm thử bằng test case cụ thể).
- [ ] Hệ thống deploy ổn định trên cloud, đã qua kiểm thử với ít nhất 2 vai trò người dùng thật (thử nghiệm nội bộ).
- [ ] Tài liệu hướng dẫn sử dụng và tài liệu trình bày (pitch deck) đã sẵn sàng.
- [ ] Không còn lỗi nghiêm trọng (critical bug) nào liên quan đến an toàn cảnh báo thuốc.

---
*Tài liệu tiếp theo: Giai đoạn 3 — Thiết kế UI/UX (User flow, Wireframe, Design system).*
