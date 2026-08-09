# 🛡️ MedGuard AI — VMEC-12

> AI Agent kiểm tra tương tác thuốc & cảnh báo an toàn dùng thuốc cho bệnh nhân và dược sĩ, dựa trên dữ liệu thật **DDInter 2.0**.

Bệnh nhân dùng nhiều thuốc/thực phẩm chức năng cùng lúc dễ gặp tương tác nguy hiểm mà không biết. MedGuard AI nhận danh sách thuốc, chuẩn hóa tên, tra cứu tương tác qua CSDL DDInter 2.0 thật (1503 thuốc / 15140 cặp tương tác), xếp hạng mức độ nghiêm trọng, giải thích bằng tiếng Việt kèm trích dẫn nguồn — và luôn có dược sĩ xác nhận (HITL) trước khi coi là đáng tin.

**AI không tự chẩn đoán, không tự khuyên đổi/ngừng thuốc — mọi cảnh báo chỉ mang tính tham khảo.**

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

## Yêu cầu môi trường

- Python **3.11+** (dự án đang chạy Python 3.12)
- Node.js **18+** và npm
- Git

---

## 1. Clone dự án

```bash
git clone <repo-url>
cd P-005
```

## 2. Cài đặt Backend

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS/Linux hoặc Git Bash trên Windows
source .venv/bin/activate   # hoặc: source .venv/Scripts/activate

pip install -r requirements.txt
```

Tạo file cấu hình:

```bash
cp .env.example .env
```

Mở `.env` và điền:
- `DEEPSEEK_API_KEY` — lấy free API key tại [platform.deepseek.com](https://platform.deepseek.com). **Không có key này, agent vẫn chạy được nhưng chỉ trả lời đúng với cặp thuốc chưa được DDInter phân loại mức độ hoặc không có trong CSDL** — các cặp có mức nhẹ/trung bình/nặng cần gọi LLM thật để sinh giải thích.
- `DATABASE_URL` — để mặc định `sqlite:///./data/app.db` cho dev, không cần đổi sang Postgres cho tới khi deploy.

## 3. Chuẩn bị dữ liệu (bắt buộc — đây là bước hay bị quên)

Dự án dùng dữ liệu tương tác thuốc **thật**, crawl từ DDInter 2.0. File gốc `vmec12_ddinter.db` **không nằm trong git** (dung lượng lớn + chưa xác minh điều khoản giấy phép để công khai) — bạn cần xin file này từ trưởng nhóm/thành viên đã có sẵn (Zalo/Drive nội bộ), rồi:

```bash
mkdir -p data/raw
# copy file vmec12_ddinter.db vào data/raw/vmec12_ddinter.db

python scripts/import_ddinter.py
```

Script sẽ tạo `data/app.db` (SQLite dev, tự sinh, cũng không nằm trong git) và nạp 1503 thuốc + 15140 cặp tương tác. Chạy lại script này bất cứ lúc nào muốn reset sạch dữ liệu dev (xóa `data/app.db` trước khi chạy lại).

> Không có file `vmec12_ddinter.db`? Backend vẫn khởi động được nhưng mọi tra cứu thuốc sẽ trả "không có dữ liệu" vì bảng `medications`/`interactions` rỗng.

## 4. Chạy Backend

```bash
uvicorn src.main:app --reload --port 8000
```

Kiểm tra: mở [http://localhost:8000/health](http://localhost:8000/health) → phải thấy `{"status":"ok",...}`. Swagger UI (danh sách API): [http://localhost:8000/docs](http://localhost:8000/docs).

## 5. Cài đặt & chạy Frontend

Mở terminal mới (giữ backend đang chạy):

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Mở [http://localhost:3000](http://localhost:3000).

## 6. Chạy test

```bash
# ở thư mục gốc, đã activate .venv
pytest tests/ -v
```

Hiện có 21 test (agent core + API), cần `data/app.db` đã được seed ở bước 3 để pass đầy đủ.

---

## Thử luồng end-to-end

1. **Đăng ký** 1 tài khoản **Bệnh nhân** → **Thêm thuốc** (thử gõ `warfarin`, `aspirin` — có autocomplete, tự nhận biệt dược/viết tắt) → **Kiểm tra tương tác**.
2. **Đăng ký** 1 tài khoản **Dược sĩ** (dùng trình duyệt ẩn danh hoặc tab khác).
3. Hiện **chưa có màn hình gán dược sĩ ↔ bệnh nhân** (ngoài phạm vi MVP) — cần gán thủ công 1 lần:

   ```bash
   python -c "import sqlite3; c=sqlite3.connect('data/app.db').cursor(); c.execute('SELECT id,ho_ten,email,vai_tro FROM users'); [print(r) for r in c.fetchall()]"

   python -c "from src.db.session import SessionLocal; from src.db.models import PharmacistAssignment; db=SessionLocal(); db.add(PharmacistAssignment(pharmacist_id='<ID_DUOC_SI>', patient_id='<ID_BENH_NHAN>')); db.commit()"
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
- Chưa deploy (chạy local, SQLite dev; Postgres/CI-CD để dành khi deploy thật).
- Chưa có OCR đơn thuốc, tương tác thuốc–bệnh nền, đa ngôn ngữ (ngoài phạm vi MVP).
- Chưa xác minh điều khoản giấy phép dữ liệu DDInter 2.0 — cần làm trước khi demo công khai.

Chi tiết đầy đủ về kiến trúc, quyết định thiết kế và roadmap từng giai đoạn: xem [`docs_giai_doan/`](docs_giai_doan/).

## License

MIT (mã nguồn) — dữ liệu DDInter 2.0 dùng cho mục đích học thuật/giáo dục, xem lưu ý ở trên.
