# Evaluation Evidence — MediCheck (VMEC-12)

Ngày chạy: 2026-08-16
Môi trường: local, `uvicorn src.main:app --port 8000`, DB thật `data/app.db` (1503 thuốc / 15140 cặp tương tác DDInter 2.0), LLM thật DeepSeek-chat (không mock).
Cách tái tạo: xem [Sample Queries](../../README.md#sample-queries) trong README — mỗi case dưới đây là 1 lệnh `curl` thật gọi `POST /api/v1/guest/medications/check`.

## 1. Manual Test Cases (5 case, output thực tế)

5 case được chọn để phủ đủ **4 mức độ** hệ thống phân loại (`nang`/`trung_binh`/`nhe`/`chua_phan_loai`), cộng thêm 1 case tái hiện đúng lỗi dữ liệu N/A đang được xử lý (xem mục 3).

| # | Input | Mức độ mong đợi (DDInter gốc) | Mức độ trả về | Có giải thích? | Pass/Fail |
|---|---|---|---|---|---|
| 1 | Dolutegravir + Iron | Major → `nang` | `nang` | ✅ | ✅ |
| 2 | Omega-3 fatty acids + Abciximab | Moderate → `trung_binh` | `trung_binh` | ✅ | ✅ |
| 3 | Acarbose + Warfarin | Minor → `nhe` | `nhe` | ✅ | ✅ |
| 4 | Cyclosporine + Folic acid | Unknown → `chua_phan_loai` | `chua_phan_loai` | ✅ (cảnh báo thận trọng, không bịa mức độ) | ✅ |
| 5 | Abciximab + Acalabrutinib | Major → `nang`, nhưng **mô tả nguồn (`Interaction`) bị thiếu trong CSDL đã tải (`N/A`)** | `nang` | ✅ (agent vẫn sinh giải thích hợp lý từ nguồn trích dẫn dù thiếu mô tả gốc) | ✅ |

**5/5 pass** — muc_do trả về đúng khớp dữ liệu DDInter gốc ở mọi case, guardrail không chặn case nào (đều có `nguon_trich_dan` hoặc lời khuyên thận trọng đi kèm).

## 2. Chi tiết từng case (request/response thật)

### Case 1 — Dolutegravir + Iron (nặng)

```bash
curl -X POST http://localhost:8000/api/v1/guest/medications/check \
  -H "Content-Type: application/json" \
  -d '{"medications":["Dolutegravir","Iron"]}'
```

- `muc_do`: `nang` · `has_severe`: `true`
- `giai_thich`: "Khi bạn dùng chung dolutegravir với các sản phẩm chứa sắt (như viên bổ máu), cơ thể sẽ hấp thu thuốc kháng virus kém hơn hẳn, khiến lượng thuốc vào máu giảm đi. Điều này có thể làm giảm hiệu quả điều trị của dolutegravir. Nguyên nhân là các thành phần kim loại trong sắt có thể "bắt giữ" thuốc trong đường tiêu hóa, không cho chúng đi vào máu. Nếu bạn đang dùng cả hai, hãy trao đổi với dược sĩ hoặc bác sĩ của mình để được hướng dẫn sắp xếp thời gian dùng thuốc hợp lý nhất."
- `nguon_trich_dan`: "[1] \"Product Information. Tivicay (dolutegravir).\" ViiV Healthcare, Research Triangle Park, NC., [2] Wohlt PD, Zheng L, Gunderson S, Balzar SA, Johnson BD, Fish JT \"Recommendations for the use of medications with continuous enteral nutrition.\" Am J Health Syst Pharm 66 (2009): 1438-67, ..." _(rút gọn, có citation thật)_

### Case 2 — Omega-3 fatty acids + Abciximab (trung bình)

```bash
curl -X POST http://localhost:8000/api/v1/guest/medications/check \
  -H "Content-Type: application/json" \
  -d '{"medications":["Omega-3 fatty acids","Abciximab"]}'
```

- `muc_do`: `trung_binh` · `has_severe`: `false`
- `giai_thich`: "Khi bạn dùng omega-3 (như dầu cá) cùng với thuốc abciximab, nguy cơ chảy máu của bạn có thể tăng lên đáng kể. Omega-3 có thể làm loãng máu thêm, cộng hưởng với tác dụng chống đông của abciximab khiến máu khó đông hơn bình thường. Nếu bạn thấy bầm tím lạ, chảy máu kéo dài hay bất kỳ dấu hiệu bất thường nào, hãy nói ngay với bác sĩ hoặc dược sĩ để được tư vấn cụ thể nhé."
- `nguon_trich_dan`: 7 nguồn thật (Cerner Multum, Blood 76 (1990), Product Information Vascepa, Arterioscler Thromb Vasc Biol 2004, ...).

### Case 3 — Acarbose + Warfarin (nhẹ)

```bash
curl -X POST http://localhost:8000/api/v1/guest/medications/check \
  -H "Content-Type: application/json" \
  -d '{"medications":["Acarbose","Warfarin"]}'
```

- `muc_do`: `nhe` · `has_severe`: `false`
- `giai_thich`: "Khi bạn dùng chung hai thuốc này, có thể làm tăng tác dụng chống đông máu của warfarin, khiến chỉ số INR dễ vượt mức an toàn. Điều này làm tăng nguy cơ chảy máu bất thường, như bầm tím, chảy máu chân răng hay nước tiểu đỏ. Nếu thấy bất kỳ dấu hiệu nào như vậy, bạn nên báo ngay cho bác sĩ hoặc dược sĩ để được kiểm tra nhé."
- `nguon_trich_dan`: 13+ nguồn thật, dẫn đầu bởi Morreale AP, Janetzky K, "Probable interaction of warfarin and acarbose", Am J Health Syst Pharm 54 (1997).

### Case 4 — Cyclosporine + Folic acid (chưa phân loại)

```bash
curl -X POST http://localhost:8000/api/v1/guest/medications/check \
  -H "Content-Type: application/json" \
  -d '{"medications":["Cyclosporine","Folic acid"]}'
```

- `muc_do`: `chua_phan_loai` · `has_unclassified`: `true`
- `giai_thich`: "DDInter chưa phân loại mức độ nghiêm trọng cho cặp thuốc này — cần thận trọng, hãy hỏi dược sĩ/bác sĩ trước khi tiếp tục dùng đồng thời."
- `nguon_trich_dan`: `"-"` (không có nguồn trong DDInter cho cặp này — guardrail không bịa citation, trả lời trung thực bằng lời khuyên thận trọng thay vì mức độ giả).

### Case 5 — Abciximab + Acalabrutinib (nặng, nhưng thiếu mô tả gốc)

```bash
curl -X POST http://localhost:8000/api/v1/guest/medications/check \
  -H "Content-Type: application/json" \
  -d '{"medications":["Abciximab","Acalabrutinib"]}'
```

- `muc_do`: `nang` · `has_severe`: `true`
- Trường `Interaction` (mô tả) gốc trong CSDL đã tải về là `N/A` cho cặp này, nhưng trường `References_info` (nguồn trích dẫn) vẫn có dữ liệu thật — agent dùng nguồn đó để sinh giải thích hợp lý thay vì báo lỗi hay bịa mô tả:
- `giai_thich`: "Khi bạn dùng chung hai loại thuốc này, nguy cơ chảy máu có thể tăng lên, ví dụ như bầm tím, chảy máu chân răng hay khó cầm máu khi bị thương. Lý do là cả hai đều có thể ảnh hưởng đến quá trình đông máu của cơ thể, nên việc kết hợp chúng cần được theo dõi kỹ. Nếu bạn thấy bất kỳ dấu hiệu chảy máu bất thường nào, hãy báo ngay cho bác sĩ hoặc dược sĩ của bạn để được hướng dẫn cụ thể."
- `nguon_trich_dan`: "[1] \"Product Information. Calquence (acalabrutinib).\" Astra-Zeneca Pharmaceuticals, Wilmington, DE., ..."

## 3. Known data gap (đang được xử lý)

Case 5 minh họa đúng vấn đề đã phát hiện khi rà soát dữ liệu: một số cặp có `Level` (mức độ) là Major/Moderate/Minor thật từ DDInter nhưng trường `Interaction` (mô tả) trong file `.db` đã tải về bị thiếu, hiện là `"N/A"`. Đã xác nhận bản online tại `ddinter2.scbdd.com` đầy đủ hơn file tải về, và đang chạy `crawl_missing_interactions.py` để lấy lại phần mô tả còn thiếu (không ảnh hưởng đến `muc_do`/mức độ, vốn đã đúng — chỉ ảnh hưởng độ chi tiết của phần mô tả nguồn trước khi LLM sinh giải thích). Agent hiện tại đã có cơ chế fallback hợp lý (dùng citation để sinh giải thích chung khi thiếu mô tả chi tiết) nên không có case nào trả lời sai hoặc bịa thông tin.

## 4. Automated Test Results

```
pytest tests/ -q
24 passed, 21 warnings in 1.17s
```

24/24 test tự động (agent core + API) pass. Trước khi fix, 5 test fail do 2 nguyên nhân riêng biệt (đã sửa cả hai):

- **4 test** (`test_explain_node_always_has_citation`, `test_explain_node_unclassified_skips_llm`, `test_check_medications_severe_pair_hides_pharmacist_fields`, `test_pharmacist_receives_review_request_and_can_review`): monkeypatch trỏ vào `src.agents.nodes.explain_node.get_llm` — nhưng `explain_node.py` đã refactor sang gọi `ainvoke_llm` (wrapper có retry/backoff trong `src/services/llm.py`) chứ không còn import `get_llm` trực tiếp, nên `monkeypatch.setattr` báo `AttributeError` (attribute không tồn tại). Fix: đổi patch target sang `ainvoke_llm` ở cả 4 test.
- **1 test** (`test_lookup_node_no_data_for_unknown_pair`): test giả định cặp Ethanol + Acetaminophen KHÔNG có dữ liệu tương tác trong CSDL (đúng tại thời điểm viết test, dựa trên `data/raw/vmec12_ddinter.db` bản đơn file cũ). Sau khi nạp thêm các nhóm ATC khác (`vmec12_ddinter_B/D/P/V&R...`), cặp này thực tế đã có dữ liệu thật (mức "nặng"). Đây là dữ liệu drift, không phải bug code. Fix: đổi sang cặp Amoxicillin + Acetaminophen — đã xác minh hiện không có dòng nào trong bảng `interactions`.

## 5. Kết luận

- 5/5 manual test case cho kết quả `muc_do` đúng với dữ liệu DDInter gốc, giải thích tiếng Việt mạch lạc, luôn có trích dẫn nguồn hoặc lời khuyên thận trọng — không có case nào agent tự bịa thông tin.
- Phát hiện 1 known data gap thật (mô tả N/A ở một số cặp Major/Moderate/Minor) — đã có kế hoạch khắc phục cụ thể (`crawl_missing_interactions.py`), không phải lỗi logic agent.
- 24/24 automated test pass sau khi fix 2 nguyên nhân gốc ở mục 4 (stale mock target + data drift trong test fixture).
