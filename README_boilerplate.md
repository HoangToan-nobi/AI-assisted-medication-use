# MediCheck

> Tóm tắt 1 câu: **Người dùng khó nhận biết các tương tác nguy hiểm trong đơn thuốc → MediCheck sử dụng AI kết hợp cơ sở dữ liệu tương tác thuốc để phát hiện, xếp mức độ và giải thích tương tác → dành cho bệnh nhân và dược sĩ.**

## Vấn đề (Problem)

Khi sử dụng nhiều thuốc cùng lúc, bệnh nhân có thể gặp **tương tác thuốc–thuốc, thuốc–thực phẩm hoặc thuốc–bệnh nền** nhưng khó tự nhận biết mức độ nguy hiểm.

* **Bệnh nhân** thường không có kiến thức chuyên môn để đánh giá tương tác giữa các thuốc trong đơn.
* Việc tự tra cứu từng cặp thuốc mất thời gian và thông tin từ nhiều nguồn có thể khó hiểu đối với người dùng phổ thông.
* Các công cụ tra cứu truyền thống thường yêu cầu nhập đúng tên thuốc, trong khi người dùng có thể nhập **sai chính tả, tên thương mại hoặc tên viết tắt**.
* Kết quả chuyên môn thường dài và khó hiểu; ngược lại, các câu trả lời AI không được grounding bằng dữ liệu đáng tin cậy có nguy cơ hallucination.
* Dược sĩ cần một công cụ hỗ trợ kiểm tra nhanh nhưng vẫn phải có **evidence/reference** để xác minh kết quả.

## Giải pháp (Solution)

**MediCheck** là ứng dụng web hỗ trợ phân tích đơn thuốc bằng AI. Sản phẩm không hoạt động theo dạng chatbot chính mà cung cấp workflow kiểm tra thuốc trực tiếp.

* **Feature 1 — Drug Normalization:** Chuẩn hóa tên thuốc, xử lý tên thương mại, alias và lỗi nhập gần đúng trước khi tra cứu.
* **Feature 2 — Interaction Detection:** Phát hiện và xếp mức độ tương tác **Drug–Drug, Drug–Food và Drug–Disease** từ cơ sở dữ liệu.
* **Feature 3 — AI Explanation:** LLM tạo giải thích ngắn gọn về tương tác, cơ chế, ảnh hưởng lâm sàng và cách xử trí dựa trên evidence được truy xuất.
* **Feature 4 — Evidence & References:** Hiển thị nguồn tham khảo để người dùng và dược sĩ có thể kiểm chứng thông tin.
* **Feature 5 — Interaction Graph:** Trực quan hóa quan hệ giữa nhiều thuốc trong đơn và cho phép chọn đường nối để xem giải thích tương tác tương ứng.
* **Feature 6 — Pharmacist Review:** Dược sĩ có thể xem kết quả phân tích, xác nhận và bổ sung ghi chú chuyên môn.
* **Feature 7 — Safety Guardrails:** Kiểm tra đầu ra, yêu cầu citation và ngăn AI tự ý khuyến nghị người dùng thay đổi/ngừng thuốc.

## Target User

* **Primary:** Bệnh nhân đang sử dụng nhiều loại thuốc và muốn kiểm tra nhanh các tương tác có thể xảy ra trong đơn thuốc.
* **Secondary:** Dược sĩ/người có chuyên môn cần công cụ hỗ trợ phát hiện, xếp hạng và review tương tác thuốc nhanh hơn.

## Tech Stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| AI Agent       | LangGraph + LLM                              |
| AI Workflow    | Normalize → Lookup → Rank → Explain → Verify |
| Backend        | FastAPI + Python 3.11+                       |
| Frontend       | Next.js + TypeScript                         |
| Database       | PostgreSQL                                   |
| Drug Data      | DDInter + RxNorm Mapping                     |
| Evidence / RAG | DailyMed + PubMed + FDA Drug Labels          |
| DevOps         | Docker + Docker Compose + GitHub Actions     |

## AI Workflow

```text
User Medication List
        ↓
Drug Normalizer
        ↓
Interaction Lookup
        ↓
DDInter / PostgreSQL
        ↓
Severity Ranking
        ↓
Evidence Retrieval
        ↓
LLM Explanation
        ↓
Verification / Guardrails
        ↓
Interaction Graph + Results
```

Kết quả phân tích bao gồm:

```text
• Interaction
• Severity
• Mechanism
• Clinical Effect
• Management
• References
```

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-005.git
cd P-005

# 2. Setup environment
cp .env.example .env
# Edit .env with your API keys and database configuration

# 3. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start services
docker compose up --build
```

## Project Structure

```text
├── src/
│   ├── agents/
│   │   ├── graph.py          # Main LangGraph workflow
│   │   ├── state.py          # Shared graph state
│   │   ├── nodes/
│   │   │   ├── normalize.py
│   │   │   ├── lookup.py
│   │   │   ├── rank.py
│   │   │   ├── explain.py
│   │   │   └── verify.py
│   │   └── tools/
│   │       ├── drug_normalizer.py
│   │       ├── interaction_lookup.py
│   │       └── severity_ranker.py
│   ├── api/                  # FastAPI routes
│   ├── models/               # Pydantic schemas
│   ├── services/             # Business logic / RAG
│   ├── config.py             # Application settings
│   └── main.py               # Backend entry point
│
├── frontend/                 # Next.js frontend
├── data/                     # Drug interaction datasets
├── scripts/                  # Database/data processing scripts
├── tests/                    # Test suite
├── docs/                     # Documentation
├── eval/                     # Evaluation results
├── presentation/             # Demo & pitch materials
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/        # CI/CD
├── JOURNAL.md
├── WORKLOG.md
└── README.md
```

## API Endpoints

| Method | Path                    | Description                          |
| ------ | ----------------------- | ------------------------------------ |
| GET    | `/health`               | Health check                         |
| POST   | `/api/v1/normalize`     | Chuẩn hóa danh sách thuốc            |
| POST   | `/api/v1/analyze`       | Phân tích tương tác trong đơn thuốc  |
| GET    | `/api/v1/history`       | Lấy lịch sử phân tích của người dùng |
| GET    | `/api/v1/prescriptions` | Lấy danh sách đơn thuốc              |
| POST   | `/api/v1/prescriptions` | Tạo/lưu đơn thuốc                    |
| GET    | `/api/v1/notifications` | Lấy cảnh báo và thông báo            |
| POST   | `/api/v1/reviews`       | Dược sĩ xác nhận/ghi chú kết quả     |

## Database

MediCheck sử dụng **PostgreSQL** để lưu dữ liệu thuốc và tương tác.

Các nhóm dữ liệu chính:

```text
drugs
rxnorm_mapping
drug_drug
drug_food
drug_disease
```

Luồng tra cứu cơ bản:

```text
Input Drug
    ↓
RxNorm / Drug Normalization
    ↓
Canonical Drug
    ↓
PostgreSQL
    ├── Drug–Drug Interaction
    ├── Drug–Food Interaction
    └── Drug–Disease Interaction
```

## Safety

MediCheck là **công cụ hỗ trợ cung cấp thông tin**, không thay thế bác sĩ hoặc dược sĩ.

Hệ thống áp dụng các guardrail:

* Không tự động yêu cầu bệnh nhân ngừng hoặc thay đổi thuốc.
* Các kết luận quan trọng phải có evidence/reference.
* Phân biệt dữ liệu lấy trực tiếp từ database và nội dung được AI giải thích.
* Cảnh báo khi thuốc không thể chuẩn hóa hoặc không có trong cơ sở dữ liệu.
* Các tương tác nghiêm trọng được ưu tiên hiển thị.
* Kết quả AI có thể được dược sĩ review trước khi sử dụng trong quyết định chuyên môn.

## Deliverables Checklist

* [x] Source Code (GitHub)
* [x] README.md
* [x] Architecture Diagram (`docs/architecture_diagram.md`)
* [x] AI Logs (auto-collected)
* [x] PostgreSQL Drug Database
* [x] Drug Normalization / RxNorm Mapping
* [x] Drug–Drug Interaction Data
* [x] Drug–Food Interaction Data
* [x] Drug–Disease Interaction Data
* [ ] Live URL / Deploy
* [ ] Video Demo
* [ ] Pitch Deck (`presentation/`)
* [x] Weekly Journal (`JOURNAL.md`)
* [x] Worklog (`WORKLOG.md`)
* [ ] Evaluation Evidence (`eval/results/`)

## Team

| Member | Role              | Student ID |
| ------ | ----------------- | ---------- |
| [Name] | AI / Backend      | [ID]       |
| [Name] | Frontend          | [ID]       |
| [Name] | Data / Evaluation | [ID]       |

## License

