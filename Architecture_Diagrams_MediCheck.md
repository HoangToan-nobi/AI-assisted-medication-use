# ARCHITECTURE DIAGRAMS — MEDICHECK

## 1. System Architecture Diagram — Kiến trúc hệ thống

Sơ đồ thể hiện các thành phần chính của hệ thống và kết nối giữa tầng giao diện, backend, AI Agent, cơ sở dữ liệu và dịch vụ AI bên ngoài.

```mermaid
flowchart TB
    subgraph CLIENT["Tầng giao diện - Next.js"]
        PATIENT["Giao diện bệnh nhân<br/>Nhập thuốc và xem cảnh báo"]
        PHARMACIST["Giao diện bác sĩ/dược sĩ<br/>Tra cứu và duyệt kết quả"]
        AUTH_UI["Đăng ký và đăng nhập"]
    end

    subgraph BACKEND["Tầng Backend - FastAPI"]
        API["REST API<br/>/api/v1"]
        AUTH["Xác thực và phân quyền<br/>JWT - Bệnh nhân - Dược sĩ"]
        DRUG_API["Drug API<br/>Thuốc - Hoạt chất - Tương tác"]
        HISTORY_API["History API<br/>Lịch sử kiểm tra - Đánh giá"]
        REPORT["Tổng hợp kết quả<br/>Theo thuốc và đơn thuốc"]
    end

    subgraph AGENT["Tầng AI Agent - LangGraph"]
        ORCHESTRATOR["Agent Orchestrator"]
        NORMALIZER["Drug Normalizer<br/>Chuẩn hóa tên thuốc"]
        LOOKUP["Interaction Lookup<br/>Tra cứu tương tác"]
        RANKER["Severity Ranker<br/>Xếp hạng mức độ"]
        EXPLAINER["Clinical Explainer<br/>Tạo nội dung giải thích"]
        GUARDRAIL["Safety Guardrail<br/>Kiểm tra nguồn và an toàn"]
    end

    subgraph DATA["Tầng dữ liệu"]
        DATABASE[("SQLite - SQLAlchemy")]
        DRUG_DATA[("Thuốc - Biệt dược<br/>Hoạt chất")]
        INTERACTION_DATA[("Tương tác DDInter<br/>Mức độ - Mô tả")]
        HISTORY_DATA[("Lịch sử kiểm tra<br/>Đánh giá bác sĩ/dược sĩ")]
    end

    subgraph EXTERNAL["Dịch vụ bên ngoài"]
        DEEPSEEK[["DeepSeek API<br/>Sinh giải thích"]]
    end

    PATIENT -->|"Danh sách thuốc"| API
    PHARMACIST -->|"Tra cứu và duyệt"| API
    AUTH_UI -->|"Thông tin tài khoản"| API

    API --> AUTH
    API --> DRUG_API
    API --> HISTORY_API

    DRUG_API -->|"Yêu cầu phân tích"| ORCHESTRATOR
    ORCHESTRATOR --> NORMALIZER
    NORMALIZER --> LOOKUP
    LOOKUP --> RANKER
    RANKER --> EXPLAINER
    EXPLAINER --> GUARDRAIL

    NORMALIZER <-->|"Tên thuốc và hoạt chất"| DRUG_DATA
    LOOKUP <-->|"Cặp thuốc và tương tác"| INTERACTION_DATA
    EXPLAINER <-->|"Prompt và giải thích"| DEEPSEEK

    GUARDRAIL -->|"Kết quả đã kiểm tra"| REPORT
    REPORT -->|"Kết quả JSON"| API
    API -->|"Cảnh báo và giải thích"| PATIENT
    API -->|"Kết quả chuyên môn"| PHARMACIST

    HISTORY_API <-->|"Đọc và ghi"| HISTORY_DATA
    DATABASE --- DRUG_DATA
    DATABASE --- INTERACTION_DATA
    DATABASE --- HISTORY_DATA
```

## 2. Data Flow Diagram — Luồng dữ liệu

Sơ đồ mô tả dữ liệu từ lúc người dùng nhập danh sách thuốc đến khi hệ thống trả về cảnh báo, giải thích và nguồn tham khảo.

```mermaid
flowchart TD
    USER(["Người dùng"])
    INPUT["1. Nhập danh sách thuốc"]
    VALIDATE["2. FastAPI kiểm tra dữ liệu đầu vào"]
    AUTH{"3. Yêu cầu hợp lệ?"}

    REJECT["Trả thông báo lỗi"]
    NORMALIZE["4. Chuẩn hóa biệt dược thành hoạt chất"]
    DRUG_FOUND{"5. Nhận diện được tất cả thuốc?"}

    CORRECT["Yêu cầu người dùng kiểm tra tên thuốc"]
    PAIR["6. Tạo các cặp thuốc cần kiểm tra"]
    LOOKUP["7. Tra cứu cơ sở dữ liệu DDInter"]
    FOUND{"8. Tìm thấy dữ liệu tương tác?"}

    NO_RECORD["Tạo thông báo chưa ghi nhận tương tác"]
    RANK["9. Xếp hạng mức độ tương tác"]
    GENERATE["10. DeepSeek tạo nội dung giải thích"]
    GUARD["11. Kiểm tra nguồn và nội dung an toàn"]

    SAVE[("12. Lưu lịch sử kiểm tra")]
    RESPONSE["13. FastAPI tạo kết quả JSON"]
    DISPLAY(["14. Hiển thị cảnh báo, giải thích và nguồn"])

    USER -->|"Danh sách tên thuốc"| INPUT
    INPUT -->|"Request JSON"| VALIDATE
    VALIDATE --> AUTH

    AUTH -->|"Không"| REJECT
    REJECT --> USER

    AUTH -->|"Có"| NORMALIZE
    NORMALIZE --> DRUG_FOUND

    DRUG_FOUND -->|"Không"| CORRECT
    CORRECT -->|"Nhập lại tên thuốc"| INPUT

    DRUG_FOUND -->|"Có"| PAIR
    PAIR --> LOOKUP
    LOOKUP --> FOUND

    FOUND -->|"Không"| NO_RECORD
    FOUND -->|"Có"| RANK

    RANK --> GENERATE
    GENERATE --> GUARD

    NO_RECORD --> SAVE
    GUARD --> SAVE
    SAVE --> RESPONSE
    RESPONSE -->|"Response JSON"| DISPLAY
    DISPLAY --> USER
```

## 3. Agent Flow Diagram — Luồng xử lý của LangGraph Agent

Sơ đồ thể hiện các node, điều kiện rẽ nhánh, vòng lặp sửa kết quả và bước Human-in-the-loop trong AI Agent.

```mermaid
flowchart TD
    START(["START<br/>Nhận danh sách tên thuốc"])
    NORMALIZE["Node 1: Normalize Drug<br/>Chuẩn hóa biệt dược thành hoạt chất"]
    VALID_DRUG{"Chuẩn hóa thành công?"}
    REQUEST_EDIT["Yêu cầu người dùng kiểm tra tên thuốc"]

    LOOKUP["Node 2: Lookup Interaction<br/>Tạo từng cặp thuốc và tra cứu DDInter"]
    FOUND{"Tìm thấy dữ liệu tương tác?"}
    NO_DATA["Tạo trạng thái chưa ghi nhận tương tác"]

    RANK["Node 3: Rank Severity<br/>Critical - Major - Moderate - Minor"]
    EXPLAIN["Node 4: Generate Explanation<br/>Chuẩn bị dữ liệu và prompt"]
    DEEPSEEK[["DeepSeek API"]]

    GUARD["Node 5: Safety Review<br/>Kiểm tra nguồn, mức độ và ngôn ngữ"]
    PASS{"Kết quả đạt guardrail?"}
    REWRITE["Node 6: Rewrite Response<br/>Sửa nội dung không an toàn hoặc còn thiếu"]
    RETRY{"Vượt quá số lần viết lại?"}

    SEVERE{"Mức độ Critical hoặc Major?"}
    HITL["Human-in-the-loop<br/>Dược sĩ xác nhận kết quả"]
    COMPOSE["Node 7: Compose Result<br/>Tổng hợp mức độ, giải thích, nguồn và cảnh báo"]
    SAVE["Lưu trạng thái và lịch sử kiểm tra"]

    ERROR(["END ERROR<br/>Trả lỗi có kiểm soát"])
    END(["END<br/>Trả kết quả cuối cùng"])

    START --> NORMALIZE
    NORMALIZE --> VALID_DRUG

    VALID_DRUG -->|"Không"| REQUEST_EDIT
    REQUEST_EDIT -->|"Không thể tiếp tục"| ERROR
    REQUEST_EDIT -->|"Người dùng nhập lại"| NORMALIZE

    VALID_DRUG -->|"Có"| LOOKUP
    LOOKUP --> FOUND

    FOUND -->|"Không"| NO_DATA
    NO_DATA --> COMPOSE

    FOUND -->|"Có"| RANK
    RANK --> EXPLAIN
    EXPLAIN -->|"Prompt và dữ liệu tương tác"| DEEPSEEK
    DEEPSEEK -->|"Bản giải thích"| GUARD

    GUARD --> PASS
    PASS -->|"Không"| REWRITE
    REWRITE --> RETRY
    RETRY -->|"Chưa"| GUARD
    RETRY -->|"Rồi"| HITL

    PASS -->|"Có"| SEVERE
    SEVERE -->|"Có"| HITL
    SEVERE -->|"Không"| COMPOSE

    HITL -->|"Được duyệt"| COMPOSE
    HITL -->|"Bị từ chối"| ERROR

    COMPOSE --> SAVE
    SAVE --> END
```

## Mô tả ngắn

- **System Architecture Diagram:** mô tả các thành phần và kết nối trong toàn bộ hệ thống MediCheck.
- **Data Flow Diagram:** mô tả hướng di chuyển và quá trình biến đổi dữ liệu.
- **Agent Flow Diagram:** mô tả chi tiết các node, conditional edges, vòng lặp và Human-in-the-loop của LangGraph Agent.
