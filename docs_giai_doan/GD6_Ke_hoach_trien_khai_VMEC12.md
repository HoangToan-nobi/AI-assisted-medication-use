# GIAI ĐOẠN 6: KẾ HOẠCH TRIỂN KHAI THEO GIAI ĐOẠN
## Đề tài VMEC-12 — MedGuard AI


> **Ghi chú cập nhật 01/09/2026:** đây là tài liệu giai đoạn, giữ nguyên để đối chiếu
> quá trình. Vị trí file deliverable đã đổi theo yêu cầu BTC: sơ đồ kiến trúc →
> [`../docs/architecture.md`](../docs/architecture.md), nhật ký tuần →
> [`../docs/journal.md`](../docs/journal.md), worklog → [`../docs/worklog.md`](../docs/worklog.md),
> báo cáo đánh giá → [`../docs/evaluation.md`](../docs/evaluation.md). Dữ liệu mô phỏng
> (`data/seed/`) đã được thay hoàn toàn bằng DDInter 2.0 thật, và phần đánh giá LLM dùng
> LLM-as-judge + soát tay thay cho RAGAS như dự kiến ban đầu.

> Tài liệu này nối tiếp GD1–GD5 (đã có trên nhánh `origin/feature/medguard-agent-sprint1`) và quyết định dùng dữ liệu thật **DDInter 2.0** (1503 thuốc, 15140 cặp tương tác) thay cho seed mô phỏng — chốt trong phiên làm việc trước. Mỗi giai đoạn phụ thuộc giai đoạn trước, đặc biệt Giai đoạn 1→2→3 phải theo đúng thứ tự vì code agent/API phụ thuộc trực tiếp vào schema dữ liệu.

---

## Giai đoạn 0 — Khởi tạo nền trên `feature/demo`
**Mục tiêu:** đưa toàn bộ phần đã có sẵn vào nhánh làm việc, không phải làm lại từ đầu.

- [ ] Merge/cherry-pick từ `origin/feature/medguard-agent-sprint1` vào `feature/demo`: `src/agents/`, `src/db/`, `src/services/`, `docs_giai_doan/`, `frontend/`, `tests/`, `requirements.txt`, `docker-compose.yml`
- [ ] Tạo `.env` từ `.env.example`, điền `DEEPSEEK_API_KEY`
- [ ] `pip install -r requirements.txt`; chạy `bash scripts/setup_hooks.sh` (AI usage logging bắt buộc theo template)
- [ ] Sanity check: `pytest tests/test_agents/` pass với seed cũ **trước khi** đổi sang data thật (để biết baseline còn chạy được)

## Giai đoạn 1 — Tích hợp dữ liệu thật DDInter 2.0
**Mục tiêu:** thay seed mô phỏng bằng dữ liệu thật, theo schema đã thiết kế.

- [ ] Copy `vmec12_ddinter.db` vào `data/raw/` trong repo
- [ ] Thêm cột `mo_ta` (Text) vào model `Medication` trong `src/db/models.py`
- [ ] Thêm model mới `Interaction` (SQLAlchemy): `muc_do`, `mo_ta`, `xu_tri`, `nguon_trich_dan`, `thay_the_a/b`, unique index `(medication_a_id, medication_b_id)`
- [ ] Viết script `scripts/import_ddinter.py`: đọc `drugs`/`interactions` → chuẩn hóa `id_a < id_b` → map `Level` (Major/Moderate/Minor/Unknown → nang/trung_binh/nhe/chua_phan_loai) → ghi vào SQLite dev qua `init_db()`
- [ ] Xây bảng alias nhỏ thủ công (viết tắt phổ biến → Drug_ID thật)
- [ ] Test ETL: sau seed đúng 1503 thuốc / 15140 tương tác, không trùng cặp

## Giai đoạn 2 — Cập nhật Agent core cho data thật
**Mục tiêu:** 5 node + 3 tool hoạt động đúng với schema/nguồn dữ liệu mới.

- [ ] `drug_normalizer_tool.py`: đổi từ dict cứng sang query bảng `medications` + bảng alias
- [ ] `interaction_lookup_tool.py`: đổi từ Chroma full-scan sang SQL query theo cặp id đã sort
- [ ] `severity_ranker_tool.py`: thêm `chua_phan_loai` vào `_SEVERITY_ORDER`, thêm cờ `has_unclassified`
- [ ] `state.py`: thêm field `has_unclassified` vào `MedCheckState`
- [ ] `explain_node.py`: nhánh riêng cho `chua_phan_loai` (câu cố định, không gọi LLM diễn giải sâu) + truncate `Interaction`/`References_info` dài trước khi đưa vào prompt
- [ ] `guardrail_node.py`: bổ sung `_BANNED_PATTERNS` cho cụm tiếng Anh tương đương
- [ ] Cập nhật `tests/test_agents/test_graph.py`: chọn vài cặp thật từ DDInter làm test case cố định thay cho data mock

## Giai đoạn 3 — Backend API & DB wiring
**Mục tiêu:** đủ endpoint nghiệp vụ, nối DB, phân quyền.

- [ ] `src/models/schemas.py`: thêm `MedicationCheckRequest/Response`, `LoginRequest/Response`, `PharmacistReviewRequest`
- [ ] `src/api/routes.py`: thêm `/api/v1/auth/login`, `/api/v1/patients/{id}/medications`, `/api/v1/medications/check`, `/api/v1/medications/search`, `/api/v1/pharmacist/{id}/patients`, `/api/v1/pharmacist/reviews`
- [ ] Nối `get_db()` (`src/db/session.py`) vào route cần DB; gọi `init_db()` khi startup (`src/main.py`)
- [ ] Auth đơn giản theo 2 vai trò + middleware phân quyền route
- [ ] Escalation: khi `has_severe=true` → ghi nhận để dược sĩ phụ trách (qua `pharmacist_assignments`) thấy ưu tiên đầu danh sách
- [ ] Test API: TC-A01→TC-A05 (theo GD5) + case auth/escalation mới

## Giai đoạn 4 — Frontend (2 vai trò)
**Mục tiêu:** điền UI theo wireframe GĐ3, hiện có toàn TODO.

- [ ] `frontend/lib/api.ts`: hoàn thiện các hàm gọi API còn thiếu
- [ ] `AlertCard.tsx`: style theo `muc_do` (icon + màu + chữ mô tả, không chỉ màu); ẩn field `xu_tri` (Management) nếu không phải vai trò dược sĩ
- [ ] `(patient)/dashboard`, `medications`, `check-result`: điền nội dung
- [ ] `(pharmacist)/patients`, `review`: điền nội dung, badge ưu tiên cảnh báo nặng
- [ ] Disclaimer y tế cố định trên mọi màn hình cảnh báo
- [ ] Autocomplete tên thuốc (gọi `/api/v1/medications/search`)

## Giai đoạn 5 — HITL & Guardrail, kiểm thử an toàn
- [ ] Red-team guardrail (kịch bản 4 GD5): câu dẫn dụ đổi/ngừng thuốc → agent phải từ chối
- [ ] Dược sĩ xác nhận/ghi chú → trạng thái `da_xac_nhan` phản hồi ngược bệnh nhân
- [ ] Đo thời gian phản hồi thực tế (<5s, NFR-01) với 15k dòng thật
- [ ] Test "thuốc ngoài CSDL" → đúng cảnh báo giới hạn dữ liệu

## Giai đoạn 6 — QA toàn diện
- [ ] Toàn bộ test tự động pass theo Exit Criteria GD5
- [ ] Beta test thủ công 4 kịch bản GD5
- [ ] Eval RAGAS (độ chính xác retrieval, độ trung thực) → điền `eval/results/report.md`
- [ ] Rà soát license/trích dẫn DDInter trước khi demo công khai

## Giai đoạn 7 — Deploy
- [ ] Chuyển `database_url` sang PostgreSQL cho production
- [ ] CI/CD qua khung có sẵn trong `.github/`
- [ ] Deploy backend+frontend (Render/Railway/Fly.io/Vercel — hướng dẫn free-tier ở `docs/guide/free-accounts.md`)
- [ ] Biến môi trường thật, healthcheck `/health`

## Giai đoạn 8 — Nâng cao (sau MVP)
- [ ] OCR quét đơn thuốc
- [ ] Tương tác thuốc–bệnh nền
- [ ] Đa ngôn ngữ
- [ ] Dùng `thay_the_a/b` cho tính năng "gợi ý thay thế/trùng hoạt chất" (chỉ hiển thị dược sĩ, không để agent tự đề xuất)
- [ ] Dùng lại ChromaDB cho semantic search khi người dùng mô tả tự do

## Giai đoạn 9 — Demo Day / bàn giao
- [ ] README chính thức thay `README_boilerplate.md`
- [ ] Điền `ARCHITECTURE.md`
- [ ] Video demo, pitch deck
- [ ] Cập nhật liên tục `JOURNAL.md`, `WORKLOG.md`
- [ ] Live URL
