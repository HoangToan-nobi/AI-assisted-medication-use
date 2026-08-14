# 🛡️ MediCheck — VMEC-12 (Setup qua Docker)

> AI Agent kiểm tra tương tác thuốc & cảnh báo an toàn dùng thuốc cho bệnh nhân và dược sĩ, dựa trên dữ liệu thật **DDInter 2.0**.

Bệnh nhân dùng nhiều thuốc/thực phẩm chức năng cùng lúc dễ gặp tương tác nguy hiểm mà không biết. MediCheck nhận danh sách thuốc, chuẩn hóa tên, tra cứu tương tác qua CSDL DDInter 2.0 thật (1503 thuốc / 15140 cặp tương tác), xếp hạng mức độ nghiêm trọng, giải thích bằng tiếng Việt kèm trích dẫn nguồn — và luôn có dược sĩ xác nhận (HITL) trước khi coi là đáng tin.

**AI không tự chẩn đoán, không tự khuyên đổi/ngừng thuốc — mọi cảnh báo chỉ mang tính tham khảo.**

Guide này setup bằng **Docker** — không cần cài Python/Node trên máy, chỉ cần Docker. Chạy được trên **Windows, macOS, Linux**.

---

## Tech stack

| Layer | Công nghệ |
|---|---|
| Agent | LangGraph + LangChain, 5 node (chuẩn hóa → tra cứu → xếp hạng → giải thích → guardrail) |
| LLM | DeepSeek-chat (qua `langchain-openai` trỏ base_url DeepSeek) |
| Backend | FastAPI + Uvicorn + SQLAlchemy |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Dữ liệu tương tác thuốc | DDInter 2.0 thật (không phải mô phỏng) — xem [docs_giai_doan/GD6](docs_giai_doan/GD6_Ke_hoach_trien_khai_VMEC12.md) |
| Frontend | Next.js 14 (App Router) + TypeScript, 2 vai trò (bệnh nhân/dược sĩ) |
| Testing | pytest + pytest-asyncio + httpx (21 test) |

---

## 0. Cài Docker

Chỉ cần **một** thứ này, không cần cài Python hay Node.js riêng.

- **Windows**: cài [Docker Desktop](https://www.docker.com/products/docker-desktop/). Bật WSL2 backend khi được hỏi (mặc định). Sau khi cài xong, mở Docker Desktop và để nó chạy nền.
- **macOS**: cài [Docker Desktop](https://www.docker.com/products/docker-desktop/) (bản Apple Silicon hoặc Intel tùy máy).
- **Linux**: cài [Docker Engine](https://docs.docker.com/engine/install/) + plugin Compose (`docker compose`, không có dấu gạch ngang), theo hướng dẫn cho distro của bạn (Ubuntu/Debian/Fedora...).

Kiểm tra đã cài đúng — mở terminal (PowerShell trên Windows, Terminal trên macOS/Linux):

```bash
docker --version
docker compose version
```

Cả hai lệnh phải in ra version, không báo lỗi "command not found".

> Nếu máy bạn chỉ có `docker-compose` (có gạch ngang, bản cũ) thay vì `docker compose`, thay mọi lệnh `docker compose ...` bên dưới bằng `docker-compose ...` — cú pháp giống hệt.

---

## 1. Lấy code

```bash
git clone <repo-url>
cd P-005
git checkout feature/demo   # hoặc branch bạn được giao
git pull
```

## 2. Đặt file dữ liệu `app.db` (bắt buộc — bước hay bị quên)

File `data/app.db` (~280MB, đã seed sẵn 1503 thuốc + 15140 cặp tương tác DDInter 2.0) **quá nặng nên không nằm trong git** — bạn nhận file này qua bản zip gửi riêng (Zalo/Drive), **không phải** từ `git pull`.

1. Giải nén file zip bạn nhận được.
2. Copy file `app.db` vào đúng đường dẫn `data/app.db` ở thư mục gốc dự án (cùng cấp với `Dockerfile`).

```
P-005/
├── data/
│   └── app.db      ← đặt file ở đây
├── Dockerfile
├── docker-compose.yml
└── ...
```

Nếu thư mục `data/` chưa tồn tại thì tự tạo trước khi copy file vào.

> Không có file `app.db`? Backend vẫn khởi động được nhưng mọi tra cứu thuốc sẽ trả "không có dữ liệu" vì bảng `medications`/`interactions` rỗng — xin lại file từ người đã gửi zip.

## 3. Tạo file cấu hình `.env`

```bash
# Windows PowerShell / macOS / Linux đều dùng chung 1 lệnh này (chạy ở thư mục gốc P-005)
cp .env.example .env
```

Mở `.env` bằng editor bất kỳ và điền:

- `DEEPSEEK_API_KEY` — lấy free API key tại [platform.deepseek.com](https://platform.deepseek.com). **Không có key này, agent vẫn chạy được nhưng chỉ trả lời đúng với cặp thuốc chưa được DDInter phân loại mức độ hoặc không có trong CSDL** — các cặp có mức nhẹ/trung bình/nặng cần gọi LLM thật để sinh giải thích.
- `DATABASE_URL` — để mặc định `sqlite:///./data/app.db`, khớp với file bạn đặt ở bước 2, không cần đổi sang Postgres cho tới khi deploy thật.

Frontend không cần file `.env.local` riêng khi chạy Docker — `docker-compose.yml` đã tự trỏ `NEXT_PUBLIC_API_URL=http://localhost:8000` cho container frontend.

## 4. Build & chạy toàn bộ hệ thống

Ở thư mục gốc `P-005` (nơi có `docker-compose.yml`):

```bash
docker compose up --build
```

Lệnh này build 2 image (backend FastAPI + frontend Next.js) và chạy cả hai cùng lúc. Lần đầu sẽ mất vài phút (tải base image, cài dependencies).

Muốn chạy nền (không giữ terminal) thì thêm `-d`:

```bash
docker compose up --build -d
```

## 5. Kiểm tra đã chạy đúng

- Backend health check: mở [http://localhost:8000/health](http://localhost:8000/health) → phải thấy `{"status":"ok",...}`.
- Swagger UI (danh sách API): [http://localhost:8000/docs](http://localhost:8000/docs).
- Frontend: mở [http://localhost:3000](http://localhost:3000).

Nếu chạy `-d` (nền), xem log để debug:

```bash
docker compose logs -f              # cả 2 service
docker compose logs -f backend      # chỉ backend
docker compose logs -f frontend     # chỉ frontend
```

## 6. Dừng hệ thống

```bash
docker compose down
```

Lệnh này dừng và xóa container, nhưng **không** xóa `data/app.db` (vì nó được mount từ máy thật qua volume, không nằm trong container).

## 7. Chạy test (tùy chọn)

Test chạy bên trong container backend đang sống:

```bash
docker compose exec backend pytest tests/ -v
```

Hiện có 21 test (agent core + API), cần `data/app.db` đã đặt ở bước 2 để pass đầy đủ.

---

## Lệnh hay dùng — tóm tắt

| Việc cần làm | Lệnh |
|---|---|
| Build lại + chạy | `docker compose up --build` |
| Chạy nền | `docker compose up --build -d` |
| Xem log | `docker compose logs -f` |
| Dừng | `docker compose down` |
| Restart 1 service | `docker compose restart backend` |
| Vào shell container backend | `docker compose exec backend bash` |
| Chạy test | `docker compose exec backend pytest tests/ -v` |
| Build lại từ đầu (không cache) | `docker compose build --no-cache` |

---

## Thử luồng end-to-end

1. **Đăng ký** 1 tài khoản **Bệnh nhân** → **Thêm thuốc** (thử gõ `warfarin`, `aspirin` — có autocomplete, tự nhận biệt dược/viết tắt) → **Kiểm tra tương tác**.
2. **Đăng ký** 1 tài khoản **Dược sĩ** (dùng trình duyệt ẩn danh hoặc tab khác).
3. Hiện **chưa có màn hình gán dược sĩ ↔ bệnh nhân** (ngoài phạm vi MVP) — cần gán thủ công 1 lần, chạy trong container backend:

   ```bash
   docker compose exec backend python -c "import sqlite3; c=sqlite3.connect('data/app.db').cursor(); c.execute('SELECT id,ho_ten,email,vai_tro FROM users'); [print(r) for r in c.fetchall()]"

   docker compose exec backend python -c "from src.db.session import SessionLocal; from src.db.models import PharmacistAssignment; db=SessionLocal(); db.add(PharmacistAssignment(pharmacist_id='<ID_DUOC_SI>', patient_id='<ID_BENH_NHAN>')); db.commit()"
   ```

4. Đăng nhập lại bằng tài khoản dược sĩ → **Bệnh nhân phụ trách** → xem cảnh báo, ghi chú, xác nhận.

---

## Cấu trúc dự án

```
src/
├── agents/
│   ├── graph.py, state.py       # LangGraph: 5 node nối tiếp
│   ├── nodes/                   # normalize → lookup → rank → explain → guardrail
│   └── tools/                   # drug_normalizer, interaction_lookup, severity_ranker
├── api/
│   ├── routes.py                # toàn bộ endpoint /api/v1/*
│   └── deps.py                  # auth dependency (get_current_user, require_role)
├── db/
│   ├── models.py                # SQLAlchemy: users, medications, interactions, ...
│   └── session.py
├── models/schemas.py             # Pydantic request/response
├── services/auth.py, llm.py, vector_store.py
├── config.py, main.py
scripts/import_ddinter.py         # ETL: data/raw/vmec12_ddinter.db -> data/app.db
frontend/                         # Next.js App Router, 2 route group (patient)/(pharmacist)
tests/                            # pytest — agent core + API
docs_giai_doan/                   # Tài liệu thiết kế GD1-GD6 (ý tưởng, BRD/SRS, UI/UX, MVP, QA, roadmap)
```

## API chính (`/api/v1`)

| Method | Path | Vai trò | Mô tả |
|---|---|---|---|
| POST | `/auth/register`, `/auth/login` | công khai | Đăng ký/đăng nhập |
| GET | `/medications/search?q=` | đã đăng nhập | Autocomplete tên thuốc (khớp cả alias) |
| GET/POST/DELETE | `/patients/{id}/medications` | bệnh nhân | Hồ sơ thuốc đang dùng |
| POST | `/medications/check` | bệnh nhân | Chạy agent, lưu kết quả, trả về (ẩn field dược sĩ) |
| GET | `/patients/{id}/checks[/{check_id}]` | bệnh nhân | Lịch sử kiểm tra |
| GET | `/pharmacist/{id}/patients` | dược sĩ | DS bệnh nhân phụ trách, escalate cảnh báo nặng |
| GET | `/pharmacist/patients/{id}/checks` | dược sĩ | DS lần kiểm tra của 1 bệnh nhân |
| GET/POST | `/pharmacist/reviews[/{check_id}]` | dược sĩ | Xem đầy đủ (có `xu_tri`) + xác nhận |

## Giới hạn hiện tại (biết trước, chưa phải bug)

- Chưa có UI admin gán dược sĩ ↔ bệnh nhân (làm thủ công qua DB, xem mục "Thử luồng end-to-end").
- Chưa deploy (chạy local qua Docker, SQLite dev; Postgres/CI-CD để dành khi deploy thật).
- Chưa có OCR đơn thuốc, tương tác thuốc–bệnh nền, đa ngôn ngữ (ngoài phạm vi MVP).
- Chưa xác minh điều khoản giấy phép dữ liệu DDInter 2.0 — cần làm trước khi demo công khai.

## Xử lý sự cố (troubleshooting)

- **`docker: command not found` / Docker Desktop không mở được**: cài lại theo bước 0, trên Windows đảm bảo đã bật WSL2 và virtualization trong BIOS.
- **Port 8000 hoặc 3000 đã bị chiếm**: tắt app khác đang dùng port đó, hoặc sửa cổng map trong `docker-compose.yml` (ví dụ `"8001:8000"`).
- **Backend báo lỗi không tìm thấy `data/app.db` hoặc tra cứu thuốc luôn rỗng**: kiểm tra lại bước 2 — file phải nằm đúng `data/app.db`, không phải `data/app.db.zip` hay `data/app/app.db`.
- **Trên Linux, backend báo lỗi permission denied khi đọc/ghi `data/app.db`**: chạy `chmod 664 data/app.db` (và `chmod 775 data/` nếu cần) ở máy host rồi `docker compose restart backend`.
- **Sửa code nhưng không thấy đổi**: backend đã bật `--reload` và mount `./src:/app/src` nên tự nhận thay đổi; frontend chạy `npm run dev` và mount `./frontend:/app` nên cũng tự nhận. Nếu vẫn không thấy, thử `docker compose restart` hoặc `docker compose up --build`.
- **Muốn xóa sạch làm lại từ đầu** (không xóa `data/app.db`): `docker compose down` rồi `docker compose up --build --force-recreate`.

Chi tiết đầy đủ về kiến trúc, quyết định thiết kế và roadmap từng giai đoạn: xem [`docs_giai_doan/`](docs_giai_doan/).

## License

MIT (mã nguồn) — dữ liệu DDInter 2.0 dùng cho mục đích học thuật/giáo dục, xem lưu ý ở trên.
