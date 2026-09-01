# Kế hoạch đánh giá hệ thống LLM sinh giải thích — trạng thái

> Cập nhật: 01/09/2026. File này track riêng **mục tiêu tối thượng: đánh giá độ tin cậy
> của phần LLM sinh giải thích tương tác thuốc** (`giai_thich`) trong MediCheck, từ lúc
> sinh câu trả lời đến lúc ra quyết định go/no-go. Chi tiết từng phát hiện/số liệu nằm ở
> [`results/report.md`](results/report.md) — file này chỉ để biết **đang ở bước nào,
> bước nào xong, bước nào chưa**.
>
> Không thay thế `PLAN.md`/`STATUS.md` (bàn giao phiên trước, 31/08, còn dữ liệu κ/B1-B4
> cũ) — file này là bản kế hoạch MỚI, gọn hơn, phản ánh đúng những gì đã làm trong phiên
> 01/09 (sửa guardrail 3 lần, chạy lại 135 case, dùng subagent Claude làm judge).

**Chú giải trạng thái:** ✅ xong · 🔶 xong 1 phần · ⬜ chưa làm

---

## Giai đoạn 0 — Hạ tầng & dữ liệu (có sẵn từ trước)

- ✅ Gold-set 135 case (`drug_drug` 60, `food` 20, `disease` 20, `overview` 10,
  `red_team` 15, `edge` 10) — `eval/datasets/*.jsonl`
- ✅ Harness sinh câu trả lời (`run_eval.py`: phase `cold`/`warm`/`consistency`/`latency`)
- ✅ Rubric chấm (`faithfulness.md`/`relevance.md`/`completeness.md`/`consistency.md`)

## Giai đoạn 1 — Sinh câu trả lời (Generation)

- ✅ **Cold phase — 135/135 case** (2 mẫu ngẫu nhiên có seed, không trùng không sót:
  `half_20260901` 68 case + `rest_20260901` 67 case)
- ✅ **Warm phase — 135/135 case** — khớp 100% với cold về số lượng tương tác tìm được

## Giai đoạn 2 — Guardrail & an toàn (Safety)

- ✅ Sửa `filter_banned_language` lọc theo **từng câu** thay vì xoá cả đoạn khi dính 1
  pattern cấm
- ✅ Tinh chỉnh pattern quá rộng (bỏ `"cách nhau"`/`"gần nhau"` trần trụi, thêm điều kiện
  tình thái cho pattern liều)
- ✅ Vá **3 lỗ hổng leak thật** phát hiện trong phiên này:
  1. Pattern liều thiếu điều kiện tình thái (bắt nhầm câu mô tả sự kiện) — đã sửa
  2. `"cách xa nhau ít nhất 2 giờ"` lọt qua vì không đúng 2 từ khoá cũ — đã thêm pattern
     neo bằng số+đơn vị thời gian
  3. Câu ghép `"cần [A] và ngừng [B]"` lọt qua vì "ngừng" không đứng ngay sau modal verb
     — phát hiện qua chạy **consistency** (không phải test 1 lần), đã thêm pattern neo
     modal-verb + "và" trong cùng câu
- ✅ Xác nhận **0/135 case bị nuốt trắng** thành fallback (cold+warm), **15/15 red-team
  sạch** (kể cả prompt injection), **10/10 edge case sạch**
- ⬜ **Re-run 135 case 1 lần nữa** trên code sau đợt vá cuối (#3 ở trên) để xác nhận sạch
  toàn diện — chưa bắt buộc vì cả 3 lỗ hổng đã unit-test trực tiếp bằng đúng câu leak
  thật, nhưng nên làm nếu muốn số liệu "chính thức" cuối cùng

## Giai đoạn 3 — Chấm chất lượng (Faithfulness / Relevance / Completeness)

- ✅ Tự đọc tay **135/135 case**, áp đúng rubric + đúng cách chọn "1 đoạn đại diện/case"
  mà `judge.py` dùng → faithfulness ≈0.996 (n=108), relevance 5.0/5 (n=98),
  completeness 1.00 (n=86)
- ✅ Phát hiện + sửa **2 lỗi hạ tầng trong chính `judge.py`**:
  - 3 case red-team thiếu trường `nguon` trong dataset → đã bổ sung từ DB thật
  - `_pick_narrative`/`pick_scored_item` chỉ lấy 1 dòng nguồn tĩnh, sai với sản phẩm
    nhiều hoạt chất → đổi sang đọc `mo_ta_dich`/`xu_tri_dich` (đã gộp đủ) ngay trên
    chính item đang chấm
- 🔶 **Đối chứng độc lập bằng subagent Claude làm judge** — mỗi subagent 1 case, không
  thấy case khác, không cần API key riêng: **35/135 case (26%)** đã chấm, hội tụ tốt
  với số tự chấm tay ở trên. Phát hiện thêm 1 leak thật (giai đoạn 4).
  - ⬜ Mở rộng lên phần còn lại (100/135) nếu muốn độ tin cậy cao hơn cho báo cáo chính
    thức — có thể dừng ở mức thấp hơn nếu chỉ cần "đủ tin cho kết luận định tính"
- ⬜ (Tuỳ chọn, không bắt buộc) Chạy `judge.py` thật với `deepseek-reasoner` để có bộ
  JSON verdict "chính thức", audit lại độc lập được — hiện tại toàn bộ số liệu ở trên là
  tự chấm tay + subagent, KHÔNG phải chạy đúng script gốc

## Giai đoạn 4 — Consistency (độ ổn định qua nhiều lần sinh)

- ✅ Chạy **20 case × 3 lần** trên code hiện tại (sau khi sửa guardrail): mức độ nghiêm
  trọng khớp 100% qua 3 lần, nội dung lâm sàng cốt lõi nhất quán, 0 case bị nuốt trắng
- ✅ Tìm ra + sửa lỗ hổng leak thật (#3 ở Giai đoạn 2) — chính consistency là công cụ tìm
  ra nó, không phải test 1 lần
- ⬜ Re-run consistency 1 lần nữa sau đợt vá cuối để xác nhận sạch hoàn toàn (khuyến
  nghị, không bắt buộc)

## Giai đoạn 5 — Latency

- ✅ Đo lại trên code hiện tại (`--phase latency --reps 10`): mọi kịch bản đạt ngưỡng đã
  đặt ở `report.md` §5.3 (s1 ≤3 thuốc warm p95 ≈3.3s, s2 4-6 thuốc ≈6.1s, s3 multi-Rx
  ≈4.0s, cold cao nhất 9.14s — đều dưới ngưỡng)

## Giai đoạn 6 — Con người xác nhận (Human-in-the-loop)

- ⬜ **κ (Cohen's kappa)** — cần **2 người chấm ĐỘC LẬP**, đối chứng với bộ judge/
  subagent lần này. Bản κ cũ (báo cáo 31/08) chỉ đối chứng với deepseek-reasoner, mẫu
  nhỏ (n=10-20), **không áp dụng được cho bộ số 01/09**
- ⬜ `human_review.csv` — 2 người chấm tay lại (ít nhất phần case liên quan các bug mới
  sửa) để có xác nhận an toàn cuối, độc lập với AI

## Giai đoạn 7 — Tổng hợp & quyết định

- 🔶 `report.md` — đã cập nhật §4.5 (guardrail + 135 case + 2 bug judge.py), **chưa cập
  nhật** latency/consistency mới nhất của phiên này (đo sau khi viết §4.5)
- ⬜ Ghi rõ giới hạn độ tin cậy trong bản tổng hợp cuối (subagent mới phủ 26%, không phải
  judge.py thật, chưa có κ đối chứng với bộ judge lần này)
- ⬜ Go/no-go quyết định cuối cùng, dựa trên đủ số liệu ở Giai đoạn 1-6

## Không chặn go/no-go, để sau

- ⬜ Theo dõi chi phí (token/API cost mỗi case)
- ⬜ Versioning kết quả eval theo git commit hash
- ⬜ Giám sát lỗi thật từ user sau khi lên production

---

## Tóm tắt nhanh — đang ở đâu

**Đã xong chắc chắn:** sinh câu trả lời (135/135), an toàn/guardrail (3 lỗ hổng tìm+vá),
tự chấm tay chất lượng (135/135), latency, consistency (20 case, code mới).

**Đang dở, có kết quả 1 phần:** đối chứng bằng subagent (35/135 = 26%), cập nhật
report.md (thiếu số latency/consistency mới nhất).

**Chưa bắt đầu:** κ với bộ judge/subagent hiện tại, `human_review.csv` chấm lại,
chạy `judge.py` thật (tuỳ chọn), quyết định go/no-go cuối cùng.
