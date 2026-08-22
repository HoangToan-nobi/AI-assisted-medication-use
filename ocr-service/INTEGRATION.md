# Tích hợp drug-ocr-service vào MediCheck (P-005)

Kế hoạch nối `drug-ocr-service` vào nút **"Quét OCR"** đang bị khoá trong MediCheck.

- OCR service: `/home/toan/Lab_AI_lythuyet/drug-ocr-service`
- MediCheck: `/home/toan/Documents/files/P-005-main-updated/P-005-main`

---

## Điều đã kiểm chứng trước khi lập kế hoạch

**Hai hệ thống dùng chung y hệt danh mục thuốc.** `scripts/import_products.py:32`
của MediCheck nạp bảng `products` từ `data/raw/thuoc_final_project.csv` — đúng
file mà `drug_resolver` của OCR service đang khớp, cùng cột `Ten_thuoc` /
`Hoat_chat_list`. Nghĩa là **tên thuốc khớp 1:1, không cần đồng bộ id** giữa hai
bên. Đây là điều kiện làm cho toàn bộ việc tích hợp trở nên nhỏ.

**Cả app đã nói chuyện bằng tên thuốc, không phải id.** Chuỗi dữ liệu hiện tại:

| Chỗ | Kiểu |
|---|---|
| `frontend/lib/prescription.ts:3` | `SelectedDrug = { name: string; known: boolean }` |
| `PrescriptionPanel.tsx:11` | `onAdd: (name: string, known?: boolean) => void` |
| `schemas.py:101` | `PrescriptionInput.products: list[str]` |
| `schemas.py:115` | `AddProductRequest.product_name: str` |

Nên đầu ra OCR chỉ cần là **danh sách tên thuốc + cờ `known`** là cắm thẳng vào
luồng có sẵn. Không phải sửa schema, không phải sửa DB, không phải đụng
`_resolve_products`.

**Cờ `known` đã tồn tại sẵn** và đúng thứ OCR cần: đánh dấu tên có trong danh
mục hay không.

**Hai vấn đề phải xử lý:**

1. **Trùng cổng** — cả hai service đều chạy `uvicorn ... --port 8000`
   (`docker-compose.yml:15` của MediCheck, README của OCR service). OCR service
   phải đổi sang 8001.
2. **MediCheck chưa từng nhận file upload.** `grep -rn "UploadFile\|multipart"
   src/` không ra kết quả nào. Đây sẽ là endpoint upload đầu tiên của app, nên
   phải tự viết giới hạn dung lượng/định dạng chứ không có mẫu sẵn để copy.

---

## Kiến trúc: giữ hai service riêng

Không gộp OCR vào backend MediCheck. Lý do cụ thể, không phải sở thích:

- OCR service kéo theo `torch` + `paddlepaddle` (~4 GB image, ~2 GB RAM khi
  chạy) và mất vài giây khởi động để nạp model. Backend MediCheck hiện rất nhẹ.
  Gộp vào là mọi lần deploy MediCheck đều phải gánh khối đó.
- Máy production có GPU. Tách riêng thì chỉ cần cấp GPU cho một container.
- OCR nặng CPU và chạy 4–7 s/ảnh; để chung sẽ chiếm worker của các request nhẹ.

**Browser không gọi thẳng OCR service.** Backend MediCheck đứng giữa làm proxy:

```
Browser ──(multipart + JWT)──► MediCheck backend :8000
                                      │
                                      └──(multipart)──► drug-ocr-service :8001
```

Vì OCR service **không có xác thực, không rate limit, không CORS** (đã kiểm:
`app/main.py` chỉ có exception handler, không có middleware nào). Cho browser
gọi thẳng là hở một endpoint upload không xác thực ra internet. Proxy qua
backend thì OCR service nằm trong mạng nội bộ của compose, tái dùng luôn JWT
sẵn có.

---

## Các bước

### Bước 1 — Đưa OCR service lên compose của MediCheck

- Đổi cổng mặc định OCR service sang **8001**.
- Thêm service vào `docker-compose.yml` của MediCheck, **không** publish cổng ra
  ngoài (chỉ `expose`), để chỉ backend gọi được.
- Mount `models/vgg_transformer.pth` hoặc để `scripts/fetch_models.sh` chạy lúc
  build (Dockerfile đã làm sẵn).
- Thêm biến `OCR_SERVICE_URL=http://ocr:8001` vào `.env.example` và
  `src/config.py`.

**Rủi ro cần biết:** image OCR ~4 GB. Nếu môi trường triển khai giới hạn dung
lượng, xem mục ONNX trong README của OCR service — bỏ được `torch` (~2 GB).

### Bước 2 — Endpoint proxy ở backend MediCheck

Thêm vào `src/api/routes.py`:

```
POST /api/v1/prescriptions/scan     (multipart: image, JWT bắt buộc)
```

Việc của nó:
1. Kiểm dung lượng (≤10 MB) và định dạng ảnh **từ bytes đã decode**, không tin
   `filename`/`Content-Type` client gửi. OCR service đã làm đúng việc này ở
   `app/utils/image_utils.py`; backend nên chặn sớm để không phí một chặng mạng.
2. Chuyển tiếp sang `POST {OCR_SERVICE_URL}/api/v1/drug/recognize`.
3. Rút gọn response OCR thành đúng thứ frontend cần.
4. OCR service chết → trả 503 có thông báo tiếng Việt rõ ràng, **không** để lộ
   lỗi nội bộ.

Schema trả về (thêm vào `src/models/schemas.py`):

```python
class ScannedDrug(BaseModel):
    row_number: int | None      # số thứ tự trên đơn
    ocr_text: str               # nguyên văn OCR đọc được — luôn hiển thị
    suggested_name: str | None  # khớp products.ten_thuoc, hoặc None
    known: bool                 # có trong danh mục hay không
    confidence: float

class ScanPrescriptionResponse(BaseModel):
    document_type: str          # prescription | medicine_package | unknown
    drugs: list[ScannedDrug]
    requires_confirmation: bool = True   # luôn True
```

Ánh xạ từ response OCR service:
`medications[].row_number` → `row_number`,
`medications[].ocr_drug_name` → `ocr_text`,
`medications[].candidates[0].drug_name` → `suggested_name`,
`candidates[0].score >= DRUG_MEDIUM_CONFIDENCE` → `known`.

**Không lưu ảnh xuống đĩa.** Đây là ảnh đơn thuốc có tên, tuổi, địa chỉ, chẩn
đoán của bệnh nhân. Xử lý trong bộ nhớ rồi bỏ; muốn lưu thì phải là quyết định
riêng có xét quyền riêng tư, không nằm trong bước này.

### Bước 3 — Frontend: mở nút và thêm bước duyệt

Sửa `frontend/components/PrescriptionPanel.tsx:121` — bỏ `disabled`, gắn
`<input type="file" accept="image/*" capture="environment">` ẩn (thuộc tính
`capture` cho phép mở thẳng camera trên điện thoại).

Thêm `frontend/lib/api.ts`: hàm `scanPrescription(file)` gọi endpoint mới.

**Bắt buộc có bước duyệt trước khi thêm.** Sau khi quét, hiện một modal liệt kê
từng dòng: nguyên văn OCR bên trái, tên đề xuất bên phải, checkbox chọn/bỏ, và
cho sửa tay. Chỉ khi bấm xác nhận mới gọi `onAdd(name, known)` cho từng dòng đã
chọn.

Đây **không phải** trau chuốt giao diện mà là yêu cầu bắt buộc — xem phần đo
lường bên dưới. Nó cũng đúng với nguyên tắc `requires_confirmation` mà cả hai hệ
thống đang theo.

Với dòng `known: false` (thuốc không có trong danh mục): hiện nguyên văn OCR,
ghi rõ "không có trong danh mục", và mở sẵn ô tìm kiếm để người dùng tự chọn.

### Bước 4 — Ba chỗ đặt nút

Nút "Quét OCR" hiện **chỉ tồn tại trong `PrescriptionPanel`**, dùng ở hai nơi:

- `frontend/app/(patient)/interaction/page.tsx:331` — tra cứu tương tác
- `frontend/app/(pharmacist)/pharmacist-lookup/page.tsx:108` — dược sĩ

Trang hồ sơ bệnh nhân (`(patient)/profile/page.tsx:797`) dùng
`PatientPrescriptionPanel` — một component **khác**, hiện **không có** nút OCR.
Muốn có ở cả ba chỗ như bạn nói thì phải thêm nút vào component này nữa. Luồng
của nó khác: nó ghi thẳng vào DB qua `POST /patients/{id}/medications`, không
chỉ sống trong session, nên bước duyệt càng quan trọng.

---

## Điều phải nói thẳng trước khi làm

**Độ chính xác khớp thuốc hiện tại là 67% (6/9) trên bộ đo.** Đo bằng
`scripts/eval_match.py` trên 12 dòng lấy từ hai đơn thuốc thật. Phần đọc chữ đã
tốt (CER 0.0% trên bộ eval, 6/6 dòng thuốc trên đơn thật), nhưng khâu ánh xạ tên
sang danh mục thì chưa.

Con số đó dẫn tới hai hệ quả:

1. **Bước duyệt ở Bước 3 là bắt buộc, không phải tuỳ chọn.** Cứ ba thuốc thì có
   một cái đề xuất sai. Tự động thêm vào đơn là đưa thuốc bệnh nhân không được
   kê vào hệ thống kiểm tra tương tác.
2. **Nên sửa bộ chấm điểm trước hoặc song song với tích hợp.** Ba ca trượt đã
   chẩn đoán xong nguyên nhân (xem phần cuối README). Sửa xong sẽ nâng con số
   này lên đáng kể.

**Có ca "khẳng định sai" chưa quyết.** `Nefiprazol 20 mg (Rabeprazole)` không có
trong danh mục, nhưng hệ thống trả `SaVi Rabeprazole 20` — cùng hoạt chất, cùng
hàm lượng, khác nhà sản xuất — với điểm 0.81, vượt ngưỡng tin cậy. Với kiểm tra
tương tác thì đúng; với "thuốc bệnh nhân đang cầm" thì sai. Cách xử lý ảnh hưởng
trực tiếp tới hiển thị ở Bước 3, nên cần chốt trước.

**Độ trễ 4–7 s mỗi ảnh trên CPU.** Cần trạng thái chờ tử tế ở frontend, và
timeout ở proxy nên đặt ≥30 s. Trên máy production có GPU thì đặt
`OCR_DEVICE=gpu:0`, không cần sửa code.

---

## Thứ tự đề xuất

1. Sửa bộ chấm điểm khớp thuốc (nâng 67% lên) — đã có bộ đo để làm an toàn
2. Bước 1 + 2 (compose + proxy) — kiểm được bằng `curl`, chưa cần frontend
3. Bước 3 (frontend + modal duyệt) trên trang tra cứu tương tác trước
4. Nhân ra trang dược sĩ, rồi trang hồ sơ bệnh nhân

Làm bước 1 trước vì nó quyết định bước 3 hiển thị thế nào, và vì tích hợp một
bộ khớp 67% rồi mới sửa sẽ phải làm lại giao diện duyệt.
