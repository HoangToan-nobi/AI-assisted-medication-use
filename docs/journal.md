# Nhật ký tuần — Team VMEC-12 (MediCheck)

> Deliverable #8. Mỗi tuần ghi: mục tiêu, việc đã xong, khó khăn và cách xử lý, bài học.
> Chi tiết từng ngày và từng commit: [`worklog.md`](worklog.md).
>
> Dự án chạy 5 tuần, **28/07/2026 → 01/09/2026**, tổng 143 commit trên mọi nhánh.

| Tuần | Thời gian | Commit | Trọng tâm |
|---|---|---:|---|
| 1 | 28/07 – 03/08 | 7 | Khởi tạo dự án, chốt tài liệu GD1–GD4, Sprint 1 agent |
| 2 | 04/08 – 10/08 | 8 | Thay dữ liệu mô phỏng bằng DDInter 2.0 thật, Docker, khung frontend |
| 3 | 11/08 – 17/08 | 47 | Luồng dược sĩ, biệt dược Việt Nam, chuyển sang Postgres, deploy lần đầu |
| 4 | 18/08 – 24/08 | 65 | Xác thực thật, admin, CI/CD, OCR đơn thuốc, tương tác thực phẩm/bệnh nền |
| 5 | 25/08 – 01/09 | 16 | Đánh giá chất lượng LLM 2 giai đoạn, vá guardrail, chuẩn hoá deliverable |

---

## Tuần 1 · 28/07 – 03/08

**Mục tiêu:** chốt đề tài, viết tài liệu giai đoạn (GD1–GD4) và dựng bộ khung agent chạy được.

**Đã hoàn thành**
- Khởi tạo dự án từ template, hoàn thành Sprint 1: agent 5 node + 3 tool, seed 16 bản ghi tương tác mô phỏng.
- Chốt Next.js cho frontend; vẽ sơ đồ luồng agent + guardrail trong GD3/GD4.

**Khó khăn & cách xử lý**

| Khó khăn | Cách xử lý | Kết quả |
|---|---|---|
| Chưa có nguồn dữ liệu tương tác thuốc đáng tin cho tiếng Việt | Khảo sát và chốt DDInter 2.0 làm nguồn duy nhất, thay vì để LLM tự sinh | Có nền tra cứu thật, mọi cảnh báo đều dẫn được nguồn |

**Bài học**
- Quyết định "dữ liệu trước, LLM sau" phải chốt ngay từ đầu: nó chi phối schema, prompt và cả cách đánh giá về sau.

**Kế hoạch tuần sau:** nạp dữ liệu DDInter thật vào CSDL, dựng Docker cho cả nhóm chạy giống nhau.

---

## Tuần 2 · 04/08 – 10/08

**Mục tiêu:** thay toàn bộ seed mô phỏng bằng dữ liệu thật và chạy được end-to-end trên máy mọi người.

**Đã hoàn thành**
- ETL DDInter 2.0 vào `medications` / `interactions`; bỏ hẳn file seed mô phỏng.
- Dockerfile + docker-compose cho backend và frontend; demo luồng cơ bản.
- Dựng khung giao diện, chuyển bottom bar sang sidebar.

**Khó khăn & cách xử lý**

| Khó khăn | Cách xử lý | Kết quả |
|---|---|---|
| File CSDL sau khi nạp DDInter quá nặng để đưa vào git | Gitignore `data/`, chia sẻ file qua kênh riêng và viết script ETL dựng lại được | Repo gọn, ai cũng dựng lại được CSDL từ dữ liệu gốc |
| Mỗi máy một môi trường Python/Node khác nhau | Chuyển hẳn sang Docker Compose | Cả nhóm chạy cùng một lệnh, hết lỗi "máy tôi chạy được" |

**Bài học**
- Đưa file dữ liệu lớn vào git là sai lầm khó sửa — phải chặn ngay từ commit đầu tiên.

**Kế hoạch tuần sau:** hoàn thiện luồng dược sĩ, hỗ trợ tra cứu theo tên biệt dược Việt Nam.

---

## Tuần 3 · 11/08 – 17/08

**Mục tiêu:** đưa sản phẩm từ "tra hoạt chất" thành "tra tên thuốc người Việt thật sự cầm trên tay", và deploy lần đầu.

**Đã hoàn thành**
- Nạp danh mục biệt dược Việt Nam (41.302 sản phẩm) và bảng liên kết biệt dược → hoạt chất.
- Luồng dược sĩ: nhận yêu cầu, xem bản đầy đủ, xác nhận và ghi chú.
- Chuyển CSDL từ SQLite local sang Postgres dùng chung; Docker đọc `$PORT` để deploy lên PaaS.
- README, video demo, sơ đồ kiến trúc bản đầu.

**Khó khăn & cách xử lý**

| Khó khăn | Cách xử lý | Kết quả |
|---|---|---|
| Một biệt dược có nhiều hoạt chất, tên viết rất khác nhau giữa các nguồn | Tách bảng `products` / `product_ingredients` + bảng alias, chuẩn hoá trong node `normalize` | Người dùng gõ tên hộp thuốc vẫn ra đúng cặp tương tác |
| Thời gian chờ kết quả quá lâu vì gọi LLM nhiều lần | Gộp prompt theo vai trò người đọc, thêm cache giải thích theo cạnh tương tác | Giảm rõ số lần gọi LLM cho cùng một lượt kiểm tra |

**Bài học**
- Phần "khó" của bài toán không nằm ở agent mà ở chuẩn hoá dữ liệu đầu vào của người dùng thật.

**Kế hoạch tuần sau:** xác thực thật (email + Google), phân quyền, và đưa bản chạy được lên internet.

---

## Tuần 4 · 18/08 – 24/08

**Mục tiêu:** đủ điều kiện chạy công khai — đăng nhập an toàn, CI/CD, và mở rộng phạm vi cảnh báo.

**Đã hoàn thành**
- Xác thực: đăng ký + xác minh email, đăng nhập Google, session bằng cookie HttpOnly có refresh xoay vòng và CSRF token.
- Vai trò admin: duyệt số CCHN của dược sĩ, quản lý người dùng, dữ liệu thuốc và phản hồi.
- Tương tác thuốc–thực phẩm và thuốc–bệnh nền, cá nhân hoá theo bệnh nền người dùng khai.
- Service OCR đơn thuốc tách riêng (PaddleOCR + VietOCR).
- CI/CD: workflow deploy backend lên Render và frontend lên Vercel khi push `feature/production`.

**Khó khăn & cách xử lý**

| Khó khăn | Cách xử lý | Kết quả |
|---|---|---|
| Render chặn kết nối SMTP ra ngoài nên không gửi được email xác minh | Chuyển sang gửi qua Gmail API (HTTPS), giữ SMTP cho chạy local | Email xác minh/đặt lại mật khẩu chạy được trên production |
| Service OCR nặng (~4 GB image, ~2 GB RAM) không nhét chung backend | Tách hẳn thành service riêng, deploy trên Modal scale-to-zero, backend gọi qua proxy auth | Backend giữ nhẹ, chỉ tốn credit khi thật sự có ảnh gửi lên |
| Biến `NEXT_PUBLIC_API_URL` đánh dấu Sensitive nên build local trong CI luôn lỗi rewrite | Chuyển sang remote build của Vercel thay vì build sẵn rồi `--prebuilt` | Deploy frontend tự động chạy ổn định |

**Bài học**
- Ràng buộc của hạ tầng miễn phí (chặn SMTP, giới hạn RAM, biến Sensitive) ảnh hưởng kiến trúc nhiều hơn dự tính — nên thử deploy sớm thay vì để cuối.

**Kế hoạch tuần sau:** đo chất lượng đầu ra của LLM một cách nghiêm túc trước khi demo.

---

## Tuần 5 · 25/08 – 01/09

**Mục tiêu:** trả lời được câu hỏi "giải thích do AI sinh ra có đáng tin không" bằng số liệu, và chuẩn hoá lại toàn bộ deliverable.

**Đã hoàn thành**
- Bộ harness đánh giá riêng ([`../eval/`](../eval/)): dataset 135 case phân tầng + 40 case held-out, 4 rubric, script chạy cold/warm/consistency.
- Chấm 2 giai đoạn (tối ưu → kiểm tra trên tập chưa từng dùng để sửa); kết quả chính thức: faithfulness 0,948 · relevance 4,64/5 · completeness 0,944 · safety 0,957 — [`evaluation.md`](evaluation.md).
- Vá 6 lỗi tìm được từ đợt chấm: mở rộng guardrail, chặn rò thông tin xử trí, hạ `temperature` 0,7 → 0,3.
- Tách 3 bảng tra cứu sang CockroachDB; chuyển CI sang self-hosted runner của BTC.
- Sắp xếp 10 deliverable về đúng vị trí BTC yêu cầu và đồng bộ tài liệu với code đang chạy.

**Khó khăn & cách xử lý**

| Khó khăn | Cách xử lý | Kết quả |
|---|---|---|
| Dùng DeepSeek-reasoner chấm chính model DeepSeek → thiên vị self-preference | Chấm lại bằng 24 phiên Claude độc lập, mỗi phiên một lô ~14 case | Bộ số đáng tin hơn, không cùng nhà cung cấp với model bị chấm |
| Vá lỗi ngay trên chính tập dùng để tìm lỗi → điểm bị thổi phồng | Chốt phiên bản code rồi đo lại trên 40 case held-out hoàn toàn mới | Chênh lệch chỉ 2–3% → hệ thống tổng quát hoá tốt, không phải vá vặt |
| Supabase free tier chỉ 0,5 GB, không chứa nổi 160k dòng tương tác | Tách 3 bảng tra cứu sang CockroachDB, ghép dữ liệu ở tầng Python thay vì JOIN | Cả 2 DB đều trong hạn mức miễn phí, hệ thống vẫn chạy đủ tính năng |
| GitHub Actions của tổ chức bị chặn vì billing | Chuyển toàn bộ job sang self-hosted runner của BTC | CI/CD chạy lại được, không tốn Actions minutes |

**Bài học**
- Rubric tự động không bắt được mọi thứ: lỗi "gọi tên hoạt chất thay vì tên biệt dược" chỉ lộ ra khi có người đọc tay 31 case.
- Đo trên tập đã dùng để sửa là tự lừa mình — phải giữ một tập held-out từ đầu.
- Không chỉ số nào đạt tuyệt đối, nên bước dược sĩ xác nhận không phải tính năng phụ mà là điều kiện để sản phẩm dùng được.

**Việc còn lại**
- Faithfulness (0,948) và Safety (0,957) chưa đạt ngưỡng đề ra — cần thêm một vòng vá và đo lại.
- Cần ≥ 2 người chấm độc lập để tính được κ; đợt vừa rồi chỉ có 1 người soát tay.
- Chưa có cơ chế phân công dược sĩ tự động và chưa dùng framework migration cho CSDL.
