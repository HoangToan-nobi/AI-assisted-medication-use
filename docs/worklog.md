# Worklog — Team VMEC-12 (MediCheck)

> Worklog được tổng hợp từ commit history thực tế của repository
> (`git log --all --no-merges`) và đã normalize các Git identity trùng nhau bằng
> [`.mailmap`](../.mailmap).
>
> Phạm vi thống kê bao gồm tất cả branch, kể cả các commit còn nằm trên branch riêng
> chưa merge, nhằm phản ánh đầy đủ quá trình development của team.
>
> Các duplicate commit phát sinh do rebase/cherry-pick của cùng một thay đổi được xác
> định bằng stable patch-id và đã loại 8 commit trùng. Những commit độc lập dù có cùng
> commit message vẫn được giữ lại.
>
> Commit history được dùng để chứng minh development activity và technical outputs,
> không dùng số lượng commit để suy ra effort, working hours hoặc contribution percentage.

**Giai đoạn:** 2026-07-28 → 2026-09-01<br>
**Tổng số:** 139 non-merge commits · 24 active days

Technical decisions, difficulties, solutions và lessons learned trong quá trình
development được ghi lại tại [Development Journal](./journal.md).

## Tổng hợp theo thành viên

| Thành viên | Vai trò chính | Commit | Active days | Unmerged |
|---|---|---:|---:|---:|
| Đàm Lê Minh Quân | Backend, AI Agent, DevOps & System Integration | 85 | 19 | — |
| Nguyễn Thị Tuyết Mai | Full-stack, Product Features & Data | 29 | 9 | 1 |
| Lê Thị Linh | Frontend, UI/UX & Documentation | 17 | 10 | — |
| Hoàng Sỹ Toàn | PM, AI/OCR & Data | 8 | 4 | 5 |

## Nhật ký theo ngày

### 2026-07-28

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | Create test_workflow.md | ✅ Done | `7571aa9` |
| Đàm Lê Minh Quân | Delete test_workflow.md | ✅ Done | `58c3fba` |
| Đàm Lê Minh Quân | hello just testing | ✅ Done | `a0e3bbf` |

**Tổng kết ngày:** 3 commit — Đàm Lê Minh Quân. Công việc: tạo rồi xóa `test_workflow.md` và thực hiện commit kiểm thử ban đầu.

---

### 2026-08-02

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Sỹ Toàn | feat: khoi tao du an tu template, hoan thanh Sprint 1 - MedGuard AI agent | ✅ Done · unmerged branch | `e5726a0` |
| Hoàng Sỹ Toàn | feat: hoan thanh Sprint 1 - MedGuard AI agent (5 node, 3 tool, seed 16 ban ghi tuong tac thuoc) | ✅ Done · unmerged branch | `cc90899` |
| Hoàng Sỹ Toàn | docs: cap nhat GD3/GD4 - chot Next.js, bo sung so do luong agent + guardrail 3 nhanh | ✅ Done · unmerged branch | `5bc1736` |
| Hoàng Sỹ Toàn | feat: hoan thanh Sprint 1 - MedGuard AI agent (5 node, 3 tool, seed 16 ban ghi tuong tac thuoc) | ✅ Done · unmerged branch | `88f0b68` |

**Tổng kết ngày:** 4 commit — Hoàng Sỹ Toàn. Công việc: khởi tạo dự án từ template, hoàn thiện các phiên bản Sprint 1 của MedGuard AI Agent, cập nhật tài liệu GD3/GD4 và sơ đồ agent/guardrail.

---

### 2026-08-04

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | feat: add demo of basic workflow | ✅ Done | `454fa92` |
| Hoàng Sỹ Toàn | gate1 | ✅ Done · unmerged branch | `80babf5` |
| Đàm Lê Minh Quân | feat: smoother UI, adding README_demo | ✅ Done | `14ed28f` |

**Tổng kết ngày:** 3 commit từ 2 thành viên — Đàm Lê Minh Quân, Hoàng Sỹ Toàn. Công việc: bổ sung demo workflow, hoàn thành gate 1, cải thiện UI và thêm `README_demo`.

---

### 2026-08-07

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Thị Tuyết Mai | Add VMEC12 ddinter database files | ✅ Done | `859fced` |
| Đàm Lê Minh Quân | feat: fix frontend and implement Docker | ✅ Done | `c3c9833` |

**Tổng kết ngày:** 2 commit từ 2 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai. Công việc: thêm database files của VMEC12 DDInter, sửa Frontend và triển khai Docker.

---

### 2026-08-08

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Lê Thị Linh | feat: update project | ✅ Done | `134b1a7` |
| Lê Thị Linh | update frontend with stitch | ✅ Done | `2adc558` |
| Lê Thị Linh | update frontend with stitch | ✅ Done | `409c4f8` |
| Lê Thị Linh | update name and change bottom bar to side bar | ✅ Done | `12de57c` |

**Tổng kết ngày:** 4 commit — Lê Thị Linh. Công việc: cập nhật dự án và Frontend từ Stitch, đổi tên hiển thị và chuyển bottom bar thành sidebar.

---

### 2026-08-09

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | Update app.db | ✅ Done | `c242dd1` |

**Tổng kết ngày:** 1 commit — Đàm Lê Minh Quân. Công việc: cập nhật `app.db`.

---

### 2026-08-11

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | feat: doctor flow update and UI fix bugs | ✅ Done | `5413ab4` |

**Tổng kết ngày:** 1 commit — Đàm Lê Minh Quân. Công việc: cập nhật doctor flow và sửa lỗi UI.

---

### 2026-08-12

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | feat: add drugs with prescription | ✅ Done | `c6e9bd5` |
| Đàm Lê Minh Quân | Update file README_demo for install | ✅ Done | `30bb7ba` |

**Tổng kết ngày:** 2 commit — Đàm Lê Minh Quân. Công việc: bổ sung thuốc theo đơn và cập nhật hướng dẫn cài đặt trong `README_demo`.

---

### 2026-08-13

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Thị Tuyết Mai | Add DDInter processed data files | ✅ Done | `f67e948` |
| Nguyễn Thị Tuyết Mai | chore: ignore raw dataset files | ✅ Done · unmerged branch | `de38af7` |

**Tổng kết ngày:** 2 commit — Nguyễn Thị Tuyết Mai. Công việc: thêm DDInter processed data files và cấu hình bỏ qua raw dataset files.

---

### 2026-08-14

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | update: fix prompt | ✅ Done | `8922d25` |
| Lê Thị Linh | done architecture diagram | ✅ Done | `59195de` |
| Lê Thị Linh | Update MediCheck architecture documentation | ✅ Done | `51eb73e` |
| Đàm Lê Minh Quân | update | ✅ Done | `23154a8` |
| Đàm Lê Minh Quân | update: fix bugs and fix bugs and just fix bugs | ✅ Done | `b9ae7a0` |

**Tổng kết ngày:** 5 commit từ 2 thành viên — Đàm Lê Minh Quân, Lê Thị Linh. Công việc: sửa prompt và các lỗi hệ thống, hoàn thiện architecture diagram và cập nhật tài liệu kiến trúc MediCheck.

---

### 2026-08-15

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Lê Thị Linh | update frontend v3 and sửa thêm phần dược sĩ xem hồ sơ xử lý | ✅ Done | `802654c` |
| Lê Thị Linh | update logo trang | ✅ Done | `2477081` |
| Đàm Lê Minh Quân | update | ✅ Done | `ba1d64c` |
| Nguyễn Thị Tuyết Mai | feat(frontend): cap nhat giao dien (co chu, list gui duoc si) | ✅ Done | `c612bec` |
| Nguyễn Thị Tuyết Mai | Add README_boilerplate.md | ✅ Done | `d8c1e74` |

**Tổng kết ngày:** 5 commit từ 3 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai, Lê Thị Linh. Công việc: cập nhật Frontend v3 và luồng dược sĩ xem hồ sơ, chỉnh logo và UI, bổ sung `README_boilerplate.md`.

---

### 2026-08-16

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | update: optimize the time have to wait for answers | ✅ Done | `79c0bde` |
| Đàm Lê Minh Quân | update: submit 2 deliverables - README and manual_test_cases (eval evidence) - still continue updating | ✅ Done | `ca8e9a2` |
| Đàm Lê Minh Quân | update TODO of README.md | ✅ Done | `f101457` |
| Nguyễn Thị Tuyết Mai | Add demo section to README with video link | ✅ Done | `80cc64c` |
| Nguyễn Thị Tuyết Mai | Update demo video and clean up README | ✅ Done | `02f797d` |
| Nguyễn Thị Tuyết Mai | Improve demo video thumbnail in README | ✅ Done | `43ddfb4` |
| Nguyễn Thị Tuyết Mai | docs: update README with MVP demo video section | ✅ Done | `7105eb4` |
| Lê Thị Linh | feat: refine responsive navigation and medication flows | ✅ Done | `8ed4de3` |
| Đàm Lê Minh Quân | change database from local to Postgresql | ✅ Done | `064f2e1` |
| Đàm Lê Minh Quân | fix(docker): respect $PORT env var in backend CMD for cloud deploy | ✅ Done | `e438ced` |
| Đàm Lê Minh Quân | chore(deploy): remove local data/ files from production repo tracking | ✅ Done | `66f8ff6` |

**Tổng kết ngày:** 11 commit từ 3 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai, Lê Thị Linh. Công việc: tối ưu thời gian chờ phản hồi, cập nhật deliverables/README/demo, cải thiện responsive navigation và medication flows, chuyển database sang PostgreSQL, sửa Docker `$PORT` và dọn local data khỏi production tracking.

---

### 2026-08-17

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | Update README.md | ✅ Done | `0e83e17` |
| Đàm Lê Minh Quân | Update README.md | ✅ Done | `9e62bdc` |
| Lê Thị Linh | sửa frontend | ✅ Done | `097d60a` |
| Đàm Lê Minh Quân | chore: stop tracking data/app.db, already gitignored | ✅ Done | `f48b3b2` |
| Đàm Lê Minh Quân | update | ✅ Done | `e207174` |
| Nguyễn Thị Tuyết Mai | feat: personalize disease interaction checks | ✅ Done | `0065f0f` |

**Tổng kết ngày:** 6 commit từ 3 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai, Lê Thị Linh. Công việc: cập nhật README và Frontend, ngừng tracking `data/app.db`, đồng thời bổ sung personalized disease interaction checks.

---

### 2026-08-18

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | fix: change light button now will be small in header of patient and pharmacist | ✅ Done | `e7da845` |
| Nguyễn Thị Tuyết Mai | Revise database setup instructions in README | ✅ Done | `c910bcb` |
| Nguyễn Thị Tuyết Mai | feat: separate personalized and proxy interaction checks | ✅ Done | `52d54be` |
| Nguyễn Thị Tuyết Mai | fix(repo): remove tracked db and cleanup redundant template files | ✅ Done | `4de4d5e` |
| Nguyễn Thị Tuyết Mai | fix(repo): remove tracked db and cleanup redundant template files | ✅ Done | `0d4f3a9` |
| Nguyễn Thị Tuyết Mai | Revise database setup instructions in README | ✅ Done | `20cc80c` |
| Lê Thị Linh | Update frontend UI and remove local data | ✅ Done | `4316db6` |
| Lê Thị Linh | Improve landing visuals and pharmacist review details | ✅ Done | `1a238cf` |
| Đàm Lê Minh Quân | fix: faster retrieve data from neon | ✅ Done | `5d0d00c` |
| Đàm Lê Minh Quân | update | ✅ Done | `65d69e1` |

**Tổng kết ngày:** 10 commit từ 3 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai, Lê Thị Linh. Công việc: chỉnh UI cho patient/pharmacist, cập nhật hướng dẫn database, tách personalized và proxy interaction checks, dọn database/template files, cải thiện landing/review UI và tốc độ truy xuất Neon.

---

### 2026-08-19

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Lê Thị Linh | update | ✅ Done | `e9d5d5a` |
| Đàm Lê Minh Quân | fix: many things, but main thing is the prompt, optimize the cost of calling LLM API, more detail on the explanation | ✅ Done | `16a9667` |

**Tổng kết ngày:** 2 commit từ 2 thành viên — Đàm Lê Minh Quân, Lê Thị Linh. Công việc: cập nhật UI, sửa prompt, tối ưu chi phí gọi LLM API và bổ sung chi tiết phần giải thích.

---

### 2026-08-20

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Thị Tuyết Mai | feat(auth): add secure backend authentication | ✅ Done | `e5a4f94` |
| Nguyễn Thị Tuyết Mai | feat(auth-ui): add registration and recovery flows | ✅ Done | `e258b9d` |
| Nguyễn Thị Tuyết Mai | style(forms): unify input spacing and select controls | ✅ Done | `a2b0563` |
| Nguyễn Thị Tuyết Mai | docs(auth): add deployment configuration and setup guide | ✅ Done | `cecc839` |
| Đàm Lê Minh Quân | ci: add CD workflow to build/push backend image and deploy to Render + Vercel on feature/production push | ✅ Done | `45255d7` |
| Đàm Lê Minh Quân | chore: ignore .vercel and .env* files at root and in frontend/ | ✅ Done | `2500b5e` |
| Đàm Lê Minh Quân | ci: drop GHCR build/deploy-backend job from cd.yml | ✅ Done | `920b6bd` |
| Đàm Lê Minh Quân | ci: restore GHCR build/deploy-backend job in cd.yml | ✅ Done | `484b7e3` |
| Nguyễn Thị Tuyết Mai | fix(deploy): enable production auth rollout | ✅ Done | `15983e6` |
| Nguyễn Thị Tuyết Mai | revert: undo production auth rollout [skip ci] | ✅ Done | `6dc8e8d` |
| Đàm Lê Minh Quân | chore: trigger Vercel deploy (commit author fix) | ✅ Done | `5a26360` |
| Nguyễn Thị Tuyết Mai | feat(admin): add management dashboard and operations | ✅ Done | `33c6f80` |
| Nguyễn Thị Tuyết Mai | fix(admin): address auth race and overview queries | ✅ Done | `0f26c6d` |
| Nguyễn Thị Tuyết Mai | fix(admin): cache overview and paginate drug data | ✅ Done | `ac5b2f4` |
| Nguyễn Thị Tuyết Mai | refactor(admin): reuse shared select fields | ✅ Done | `a7a7557` |
| Nguyễn Thị Tuyết Mai | delete hello | ✅ Done | `fb2e13b` |
| Đàm Lê Minh Quân | fix(auth): proxy /api through Next.js so login cookies stay same-origin | ✅ Done | `17640d9` |
| Đàm Lê Minh Quân | copy(landing): shorten hero subtitle | ✅ Done | `964840a` |
| Đàm Lê Minh Quân | fix(auth): make Google sign-in button consistent, reposition, restyle | ✅ Done | `53d8c5d` |
| Đàm Lê Minh Quân | fix(auth): stretch Google button to full width | ✅ Done | `99225ac` |
| Đàm Lê Minh Quân | fix(landing): round the theme toggle's left corner in the nav pill | ✅ Done | `f465dc5` |
| Nguyễn Thị Tuyết Mai | feat(auth): harden verification and recovery flows | ✅ Done | `69e74c9` |
| Đàm Lê Minh Quân | fix(landing): round the hero card's bottom-left corner | ✅ Done | `7418c9d` |

**Tổng kết ngày:** 23 commit từ 2 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai. Công việc: triển khai Backend authentication và các auth UI flows, chuẩn hóa form, bổ sung tài liệu deploy, cấu hình CI/CD và Vercel, phát triển admin dashboard, sửa auth/admin issues và tinh chỉnh landing UI.

---

### 2026-08-21

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | fix(email): send transactional email via Gmail API instead of SMTP | ✅ Done | `58ee8ac` |
| Nguyễn Thị Tuyết Mai | fix(ui): update auth and patient dashboard | ✅ Done | `1db5df7` |

**Tổng kết ngày:** 2 commit từ 2 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai. Công việc: chuyển transactional email sang Gmail API và cập nhật auth/patient dashboard UI.

---

### 2026-08-22

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Sỹ Toàn | feat(ocr): quét đơn thuốc, đọc thuốc và bệnh nền từ ảnh | ✅ Done | `10b7a5c` |
| Đàm Lê Minh Quân | feat(db): tach interactions/food/disease sang CockroachDB (facts DB) | ✅ Done | `89a49c1` |
| Nguyễn Thị Tuyết Mai | update UI | ✅ Done | `7d1a01c` |
| Đàm Lê Minh Quân | fix(tests): sua 3 test loi san co dang chan CI/CD deploy | ✅ Done | `9fb7d81` |
| Đàm Lê Minh Quân | fix(cd): sua deploy-frontend luon that bai do bien Sensitive + sai working-directory | ✅ Done | `1dcdbbb` |
| Đàm Lê Minh Quân | chore: add .vercelignore to exclude backend-only paths from Vercel uploads | ✅ Done | `398d7c7` |
| Đàm Lê Minh Quân | feat(ocr): tich hop OCR quet don thuoc qua Modal (proxy) + fix nhieu bug lien quan | ✅ Done | `e74a7cd` |

**Tổng kết ngày:** 7 commit từ 3 thành viên — Đàm Lê Minh Quân, Nguyễn Thị Tuyết Mai, Hoàng Sỹ Toàn. Công việc: bổ sung OCR quét đơn thuốc và tích hợp OCR qua Modal, tách interactions/food/disease sang facts DB, cập nhật UI, sửa test/CD và thêm `.vercelignore`.

---

### 2026-08-24

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | fix(frontend): vien nang landing khong troi khi zoom, bo cao mascot; auto-scroll xuong ket qua sau khi phan tich tuong tac | ✅ Done | `e45e229` |
| Đàm Lê Minh Quân | fix(frontend): vien nang landing dich sang phai, dung khoang trong ben phai khung hero | ✅ Done | `770f6e5` |
| Đàm Lê Minh Quân | fix(frontend): banner canh bao Cao Medi khong bi header sticky che khi auto-scroll | ✅ Done | `3da6d6c` |
| Đàm Lê Minh Quân | fix(frontend): dung chung scrollBelowStickyHeader o profile & pharmacist-lookup, giam gap con 36px | ✅ Done | `f63fe49` |
| Đàm Lê Minh Quân | chore: bo tai lieu GMAIL_API_SETUP cu, them anh thumbnail cho docs/presentation | ✅ Done | `96c695d` |
| Đàm Lê Minh Quân | fix(frontend): giam EXTRA_GAP_PX xuong 30px cho scrollBelowStickyHeader | ✅ Done | `023726b` |
| Đàm Lê Minh Quân | fix(frontend): giam EXTRA_GAP_PX xuong 28px cho scrollBelowStickyHeader | ✅ Done | `60f1cbe` |
| Đàm Lê Minh Quân | fix(frontend): giam EXTRA_GAP_PX xuong 24px cho scrollBelowStickyHeader | ✅ Done | `8e07371` |
| Đàm Lê Minh Quân | fix(frontend): bo nhan Can luu y o do thi, tam an banner Cao Medi cho duoc si | ✅ Done | `2517e1c` |
| Đàm Lê Minh Quân | fix(frontend): dong nhat in hoa tieu de mo ta/xu tri, hien references that trong popover nguon trich dan | ✅ Done | `4b7863c` |
| Đàm Lê Minh Quân | fix(frontend): popover Nguon trich dan hien danh sach tai lieu tham khao that (References_info tu DDInter), bo cau tong hop chung chung | ✅ Done | `005667e` |
| Đàm Lê Minh Quân | fix(backend): tom tat tong quan cua duoc si dung giong chuyen mon, bo cau moi trao doi voi duoc si/bac si | ✅ Done | `b64c9f5` |
| Đàm Lê Minh Quân | fix(frontend): mo rong Nguon tham khao that sang the thuoc-thuc pham/thuoc-benh nen | ✅ Done | `1241f54` |
| Đàm Lê Minh Quân | feat(backend+frontend): tra ve nguon tham khao goc cho the thuoc-thuc pham/thuoc-benh nen | ✅ Done | `88fc593` |
| Đàm Lê Minh Quân | fix(frontend): dong nhat mau nen/mau chu/co chu giua khoi mo ta khoa hoc va xu tri | ✅ Done | `47e1b55` |
| Đàm Lê Minh Quân | fix(backend): don cache food/disease cu (thieu nguon_trich_dan_chi_tiet) khi backend khoi dong | ✅ Done | `7f9deb1` |

**Tổng kết ngày:** 16 commit — Đàm Lê Minh Quân. Công việc: cải thiện landing và auto-scroll, chuẩn hóa các màn hình patient/pharmacist, hiển thị references thực trong popover, mở rộng nguồn tham khảo cho food/disease interactions và sửa Backend summary/cache.

---

### 2026-08-25

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | feat(frontend): doi UX duyet thuoc OCR sang chon san + sua/xoa, cap nhat landing hero | ✅ Done | `8de7cfc` |
| Đàm Lê Minh Quân | fix(frontend): dang nhap Google khong hien popup lai sau khi dong lan dau | ✅ Done | `10612ec` |
| Đàm Lê Minh Quân | fix(frontend): khoi phuc hover/active cho nut Google sau khi them overlay | ✅ Done | `12384a4` |
| Đàm Lê Minh Quân | fix(frontend): bo overlay an, hien thang nut Google that de dang nhap luon dung | ✅ Done | `c2ddc61` |
| Đàm Lê Minh Quân | fix(frontend): sua vong lap ResizeObserver gay nhap nhay chuot o nut Google | ✅ Done | `d11625e` |
| Đàm Lê Minh Quân | style(frontend): doi nut Google sang shape pill cho khop nut Dang nhap | ✅ Done | `93c9a10` |
| Đàm Lê Minh Quân | style(frontend): nut Google cao bang nut Dang nhap | ✅ Done | `af75f5b` |
| Đàm Lê Minh Quân | style(frontend): khop chieu cao nut Google chinh xac hon theo so do thuc te | ✅ Done | `d49bda2` |
| Đàm Lê Minh Quân | fix(frontend): quay lai overlay cho nut Google, giu fix vong lap ResizeObserver | ✅ Done | `d7a59ff` |
| Đàm Lê Minh Quân | revert(frontend): quay lai nut Google that hien thi ro, bo overlay | ✅ Done | `f987705` |
| Đàm Lê Minh Quân | copy(frontend): doi mo ta hero landing page | ✅ Done | `3d98ffd` |
| Đàm Lê Minh Quân | fix(frontend): khong tu chon thuoc diem thap khi duyet OCR, canh bao anh khong khop thuoc nao | ✅ Done | `8604be5` |
| Đàm Lê Minh Quân | fix(data): doc dung facts (interactions/food/disease) tu CockroachDB khi migrate ve SQLite | ✅ Done | `bdf8cbc` |
| Lê Thị Linh | docs(presentation): add Vietnamese MediCheck pitch deck | ✅ Done | `05d20aa` |

**Tổng kết ngày:** 14 commit từ 2 thành viên — Đàm Lê Minh Quân, Lê Thị Linh. Công việc: đổi UX duyệt thuốc OCR, sửa nhiều trạng thái của nút Google sign-in, cập nhật landing copy, siết lựa chọn OCR, sửa migration facts DB và bổ sung pitch deck MediCheck.

---

### 2026-08-26

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | ci(workflows): chuyen sang self-hosted runner cua BTC thay vi ubuntu-latest | ✅ Done | `739e374` |
| Đàm Lê Minh Quân | fix(ci): sua test job chay duoc tren self-hosted runner voi SQLite rieng | ✅ Done | `ec03ccd` |
| Đàm Lê Minh Quân | fix(ci): them DEEPSEEK_API_KEY cho test job | ✅ Done | `bfe2103` |
| Lê Thị Linh | feat: refine interaction results UI and responsive scrolling | ✅ Done | `0c12b65` |

**Tổng kết ngày:** 4 commit từ 2 thành viên — Đàm Lê Minh Quân, Lê Thị Linh. Công việc: chuyển CI sang self-hosted runner, sửa test job và cấu hình API key, đồng thời cải thiện interaction results UI và responsive scrolling.

---

### 2026-08-27

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Lê Thị Linh | feat(frontend): refine responsive UI and loading stability | ✅ Done | `870a530` |
| Lê Thị Linh | fix(ai-log): restore Codex hook logging on Windows | ✅ Done | `c15eb6f` |

**Tổng kết ngày:** 2 commit — Lê Thị Linh. Công việc: cải thiện responsive UI/loading stability và khôi phục Codex hook logging trên Windows.

---

### 2026-08-28

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Sỹ Toàn | OCR: sửa tách bảng thuốc, phân loại tài liệu và từ chối ảnh không đọc được | ✅ Done | `1039765` |
| Hoàng Sỹ Toàn | Delete ocr-service/INTEGRATION.md | ✅ Done | `1ae54ee` |

**Tổng kết ngày:** 2 commit — Hoàng Sỹ Toàn. Công việc: sửa OCR tách bảng thuốc, phân loại tài liệu và từ chối ảnh không đọc được; xóa tài liệu integration cũ.

---

### 2026-09-01

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Đàm Lê Minh Quân | fix(agent): siết guardrail và chặn rò thông tin xử trí sau đợt đánh giá LLM | ✅ Done | `3372198` |
| Đàm Lê Minh Quân | docs(deliverables): bổ sung Live URL, sơ đồ kiến trúc và worklog theo yêu cầu BTC | ✅ Done | `1af2a6d` |
| Đàm Lê Minh Quân | docs(architecture): đồng bộ tài liệu kiến trúc với hệ thống production | ✅ Done | `5970e1b` |
| Đàm Lê Minh Quân | docs(eval): đưa harness, dataset và kết quả đánh giá vào repo | ✅ Done | `1e5611d` |
| Đàm Lê Minh Quân | chore(frontend): xóa 3 file ảnh rác bị commit nhầm | ✅ Done | `2eb720a` |
| Đàm Lê Minh Quân | docs(eval): rút gọn eval/results còn báo cáo chính thức và số liệu gốc | ✅ Done | `d32f489` |
| Đàm Lê Minh Quân | docs(eval): gỡ 2 file theo dõi tiến độ khỏi git | ✅ Done | `0113f93` |
| Đàm Lê Minh Quân | docs(eval): sửa link cuối trỏ vào STATUS.md đã gỡ | ✅ Done | `6697405` |

**Tổng kết ngày:** 8 commit — Đàm Lê Minh Quân. Công việc: siết agent guardrail sau eval, bổ sung và sắp xếp deliverables, đồng bộ architecture docs, đưa eval harness/dataset/results vào repo và dọn các file/báo cáo không còn dùng.

---
