# GIAI ĐOẠN 1: Ý TƯỞNG & NGHIÊN CỨU
## Đề tài VMEC-12 — AI Agent Tra cứu tương tác thuốc & Cảnh báo an toàn dùng thuốc

---

## 1. Concept Note (Bản mô tả ý tưởng)

**Tên sản phẩm đề xuất:** MedGuard AI (tên tạm, có thể đổi)

**Vấn đề cốt lõi:**
Bệnh nhân — đặc biệt là người cao tuổi, người mắc bệnh mạn tính, hoặc người dùng đơn thuốc từ nhiều bác sĩ/phòng khám khác nhau — thường sử dụng đồng thời nhiều loại thuốc kê đơn, thuốc không kê đơn (OTC) và thực phẩm chức năng. Việc tự tra cứu tương tác thuốc thủ công (qua tờ hướng dẫn sử dụng hoặc hỏi Google) vừa mất thời gian, vừa dễ bỏ sót tương tác nguy hiểm hoặc hiểu sai mức độ nghiêm trọng.

**Giải pháp:**
Một AI Agent đóng vai trò "trợ lý an toàn dùng thuốc": người dùng nhập danh sách thuốc đang dùng (gõ tay hoặc quét ảnh đơn thuốc), agent sẽ:
1. Chuẩn hóa tên thuốc (kể cả tên viết tắt, biệt dược, tên mờ).
2. Tra cứu tương tác thuốc–thuốc và thuốc–thực phẩm trên cơ sở dữ liệu có nguồn.
3. Xếp hạng mức độ nghiêm trọng (nhẹ / trung bình / nặng).
4. Giải thích dễ hiểu, có trích dẫn nguồn, kèm khuyến cáo trao đổi với bác sĩ/dược sĩ khi cần.

**Điểm khác biệt:** Sản phẩm KHÔNG thay thế chẩn đoán y khoa — chỉ đóng vai trò cảnh báo tham khảo, mọi quyết định thay đổi thuốc đều do dược sĩ/bác sĩ quyết định (cơ chế Human-in-the-loop bắt buộc).

**Đối tượng hưởng lợi:** bệnh nhân đa bệnh lý, người chăm sóc người cao tuổi, dược sĩ tại nhà thuốc, phòng khám nhỏ chưa có hệ thống kiểm tra tương tác thuốc tự động.

---

## 2. Phân tích thị trường & đối thủ cạnh tranh

### 2.1 Bối cảnh thị trường
- Nhu cầu quản lý dùng thuốc an toàn tăng cao ở nhóm dân số già hóa và bệnh mạn tính (tiểu đường, tim mạch, huyết áp...).
- Tại Việt Nam, phần lớn bệnh nhân tự mua thuốc OTC hoặc thực phẩm chức năng mà không tham khảo tương tác với đơn thuốc đang dùng.
- Dược sĩ tại nhà thuốc bán lẻ thường không có công cụ tra cứu tương tác nhanh, chủ yếu dựa vào kinh nghiệm cá nhân.

### 2.2 Đối thủ / giải pháp tham khảo (quốc tế)
| Sản phẩm | Điểm mạnh | Hạn chế |
|---|---|---|
| Drugs.com Interaction Checker | CSDL lớn, uy tín, miễn phí | Chỉ tra cứu đơn giản, không cá nhân hóa, không có agent giải thích theo ngữ cảnh bệnh nhân |
| Medscape Interaction Checker | Được giới chuyên môn y tế tin dùng | Giao diện dành cho bác sĩ, không thân thiện với bệnh nhân phổ thông |
| Ứng dụng quản lý thuốc gia đình (MyTherapy, Medisafe...) | Nhắc lịch uống thuốc tốt | Không tập trung vào phát hiện tương tác chuyên sâu |

### 2.3 Khoảng trống thị trường (Gap)
- Chưa có giải pháp kết hợp: (1) cá nhân hóa theo hồ sơ thuốc từng bệnh nhân, (2) giải thích ngôn ngữ tự nhiên dễ hiểu, (3) OCR quét đơn thuốc, (4) cơ chế HITL cho dược sĩ xác nhận — trong một sản phẩm duy nhất, đặc biệt bằng tiếng Việt.

---

## 3. Chân dung người dùng (User Persona)

### Persona 1 — Bệnh nhân
- **Tên giả định:** Cô Lan, 62 tuổi
- **Bối cảnh:** Mắc tiểu đường type 2 và cao huyết áp, đang dùng 5 loại thuốc từ 2 bác sĩ khác nhau, thỉnh thoảng tự mua thêm thực phẩm chức năng bổ khớp.
- **Nỗi đau (pain point):** Lo lắng không biết các thuốc có "đánh nhau" hay không nhưng ngại hỏi bác sĩ vì sợ mất thời gian tái khám.
- **Mong muốn:** Một công cụ đơn giản, nhập tên thuốc là biết ngay có nguy hiểm không, và biết khi nào cần đi khám gấp.

### Persona 2 — Dược sĩ nhà thuốc
- **Tên giả định:** Dược sĩ Minh, 34 tuổi, quản lý một nhà thuốc tư nhân
- **Bối cảnh:** Mỗi ngày tư vấn hàng chục khách mua thuốc OTC, không có thời gian tra cứu tương tác kỹ lưỡng cho từng người.
- **Nỗi đau:** Sợ tư vấn sai gây tương tác nguy hiểm, ảnh hưởng uy tín nhà thuốc.
- **Mong muốn:** Công cụ tra cứu nhanh, đáng tin cậy, có thể xác nhận/ghi chú lại cho từng khách hàng quen.

---

## 4. Empathy Map & Customer Journey (rút gọn)

### 4.1 Empathy Map — Cô Lan (bệnh nhân)
| Khía cạnh | Nội dung |
|---|---|
| **Nghĩ & cảm nhận** | Lo lắng liệu thuốc tiểu đường, huyết áp và thực phẩm chức năng bổ khớp có "đánh nhau" không |
| **Nghe** | Nghe hàng xóm/con cái kể chuyện người quen bị biến chứng do dùng thuốc sai cách |
| **Nói & làm** | Tự tra Google, hỏi người bán thuốc, nhưng ít khi hỏi lại bác sĩ vì ngại mất thời gian tái khám |
| **Nỗi đau** | Không biết tin vào nguồn nào, sợ bị bỏ sót tương tác nguy hiểm |
| **Lợi ích mong muốn** | Một câu trả lời rõ ràng, đáng tin, biết khi nào cần đi khám gấp |

### 4.2 Customer Journey — trước/trong/sau khi dùng sản phẩm
| Giai đoạn | Trước khi có sản phẩm | Sau khi có MedGuard AI |
|---|---|---|
| Nhận biết vấn đề | Nghi ngờ mơ hồ, không hành động | Chủ động nhập danh sách thuốc để kiểm tra |
| Tra cứu | Tự tìm trên mạng, thông tin rời rạc, không có ngữ cảnh cá nhân | Nhận cảnh báo cá nhân hóa, có trích nguồn |
| Ra quyết định | Tự quyết định hoặc bỏ qua vì ngại hỏi | Có cảnh báo rõ ràng + khuyến nghị liên hệ dược sĩ/bác sĩ khi cần |
| Sau sự việc | Không biết mình đã từng ở trong tình huống rủi ro | Có lịch sử tra cứu, dược sĩ đã xác nhận, yên tâm hơn |

---

## 5. Phân tích SWOT

| | Nội dung |
|---|---|
| **Điểm mạnh (Strengths)** | Kết hợp cá nhân hóa + giải thích ngôn ngữ tự nhiên + HITL an toàn; nhắm đúng khoảng trống thị trường tiếng Việt |
| **Điểm yếu (Weaknesses)** | CSDL tương tác thuốc là dữ liệu mô phỏng (chưa phải nguồn y tế được kiểm chứng lâm sàng thật); team nhỏ (tối đa 2 người) nên nguồn lực hạn chế |
| **Cơ hội (Opportunities)** | Dân số già hóa, nhu cầu tự quản lý sức khỏe tăng; có thể hợp tác với nhà thuốc/phòng khám nhỏ chưa có công cụ tương tự |
| **Thách thức (Threats)** | Rủi ro pháp lý nếu người dùng hiểu nhầm là tư vấn y khoa chính thức; đối thủ quốc tế (Drugs.com, Medscape) đã có uy tín lâu năm |

---

## 6. Mô hình kinh doanh sơ bộ (giả thuyết ban đầu)
- **Đối tượng trả phí (giả thuyết):** mô hình B2B2C — nhà thuốc/phòng khám nhỏ trả phí thuê bao để trang bị công cụ tra cứu cho dược sĩ; bệnh nhân dùng miễn phí ở bản cơ bản.
- **Gói nâng cao (tương lai):** bệnh nhân trả phí để lưu trữ hồ sơ thuốc dài hạn, nhắc lịch, tích hợp OCR.
- *Đây là giả thuyết cần kiểm chứng thêm, không phải quyết định cuối cùng.*

---

## 7. Rủi ro pháp lý & đạo đức (Legal & Ethical Risk)
- Sản phẩm **không được** tự nhận là thiết bị y tế hay công cụ chẩn đoán — phải nêu rõ disclaimer "chỉ mang tính tham khảo, không thay thế tư vấn y khoa" ở mọi màn hình cảnh báo.
- Cần cam kết bảo mật dữ liệu sức khỏe cá nhân (PII/PHI) theo tinh thần các quy định bảo vệ dữ liệu hiện hành.
- Rủi ro AI "ảo giác" (hallucination) đưa thông tin sai về tương tác thuốc — bắt buộc mọi câu trả lời phải có trích nguồn, nếu không có nguồn thì phải từ chối trả lời thay vì suy đoán.

---

## 8. Success Metrics / KPI ban đầu
| Chỉ số | Mục tiêu tham khảo |
|---|---|
| Thời gian phản hồi trung bình/lượt tra cứu | < 5 giây |
| Tỷ lệ cảnh báo được dược sĩ xác nhận | ≥ 90% |
| Tỷ lệ câu trả lời có trích dẫn nguồn hợp lệ | 100% (bắt buộc) |
| Số lượt tra cứu hoàn tất không lỗi | ≥ 95% |

---

## 9. Câu hỏi nghiên cứu — đã chốt
| Câu hỏi | Quyết định |
|---|---|
| Nguồn dữ liệu tương tác thuốc | Dữ liệu **mô phỏng** theo cấu trúc kiểu DrugBank/RxNorm, không dùng dữ liệu y tế thật |
| Phạm vi người dùng MVP | **Cả hai vai trò** — bệnh nhân và dược sĩ/bác sĩ |
| OCR quét đơn thuốc | Xếp vào **giai đoạn nâng cao** (sau MVP cơ bản), không thuộc MVP Final ban đầu |
| Mức độ hoàn thiện sản phẩm | **MVP Final** — đầy đủ chức năng cốt lõi, sẵn sàng vận hành thật, không chỉ demo |

---
*Tài liệu tiếp theo: Giai đoạn 2 — Lập kế hoạch & Tài liệu yêu cầu (BRD/SRS, Roadmap, User Story).*
