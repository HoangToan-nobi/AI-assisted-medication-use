# Bộ đánh giá toàn trình — ảnh đơn thuốc → danh sách thuốc

Đo thứ người dùng thật sự nhận được: đưa vào tấm ảnh, hệ thống có ra đúng các
thuốc in trên tờ đơn không.

## Cách gán nhãn

Mỗi ảnh `<tên>.jpg` đi kèm một file `<tên>.txt`, **mỗi dòng một thuốc**:

```
Methyl prednisolon(Medrol 4mg)
Tacrolimus(Prograf 1mg)
Amlodipin + valsartan(Exforge 5mg + 80mg)
```

Dòng trống và dòng bắt đầu bằng `#` bị bỏ qua.

### Ba quy tắc

**1. Chép tên IN TRÊN ĐƠN, không phải tên trong cơ sở dữ liệu.**
Đơn ghi `Methyl prednisolon(Medrol 4mg)` thì chép y như vậy, đừng đổi thành
`Methylprednisolone 4 mg`. Đang đo hệ thống, không đo trí nhớ người gán nhãn.

**2. Chỉ liệt kê thuốc.**
Bỏ qua liều dùng (`Ngày uống 1 viên buổi sáng`), tên bệnh viện, chẩn đoán, lời dặn.

**3. Liệt kê ĐỦ, kể cả thuốc hệ thống bỏ sót.**
Đây là điểm dễ sai nhất. Các file `.txt` hiện tại là **bản nháp do chính hệ thống
đọc ra** — nếu nó bỏ sót một thuốc thì bản nháp cũng thiếu thuốc đó, và bạn chép
nguyên si thì phép đo sẽ không bao giờ phát hiện ra lỗi bỏ sót.

> **Phải mở ảnh gốc ra đối chiếu từng dòng.** Bản nháp chỉ để đỡ phải gõ lại.

## Chạy

```bash
python scripts/eval_end2end.py                 # tính đúng khi thuốc ra ở đề xuất đầu
python scripts/eval_end2end.py --top 3         # tính đúng khi nằm trong 3 ứng viên
python scripts/eval_end2end.py --verbose       # in từng thuốc trượt và từng dòng thừa
```

Ảnh nào chưa có `.txt` sẽ bị bỏ qua và báo rõ, nên gán nhãn được tới đâu chạy tới đó.

## Đọc kết quả

- **Recall** — trong số thuốc thật, tìm được bao nhiêu. Thiếu là **bỏ sót thuốc**.
- **Dòng thừa** — hệ thống trả về thuốc không có trên đơn. Nguy hiểm hơn bỏ sót,
  vì người dùng dễ tin theo.
- **Chênh lệch Top-1 với Top-3** — nếu Top-1 thấp mà Top-3 cao thì lỗi nằm ở khâu
  **xếp hạng**, chỉnh trọng số là sửa được, rẻ hơn nhiều so với sửa OCR.

## Quan hệ với hai bộ đo kia

| Bộ đo | Chấm khâu | Khi nào dùng |
|---|---|---|
| `eval_end2end.py` | cả đường đi | con số để báo cáo |
| `eval_match.py` | khớp danh mục | khi toàn trình tệ, tìm xem có phải do khớp sai |
| `eval_ocr.py` | đọc chữ | khi nghi OCR đọc sai chữ |

Toàn trình cho biết **có vấn đề**, hai bộ kia cho biết **vấn đề ở đâu**.

## Lưu ý về dữ liệu

Ảnh đơn thuốc chứa thông tin bệnh nhân. `ocr-service/.gitignore` chặn sẵn
`*.jpg *.jpeg *.png *.webp` nên **ảnh không lên git** — chỉ file nhãn `.txt` và
README này được commit. Ai muốn chạy lại bộ đo phải tự chuẩn bị ảnh.

Nên **che tên, số CCCD, số BHYT, số điện thoại** trên ảnh trước khi chia sẻ cho
người khác trong nhóm.
