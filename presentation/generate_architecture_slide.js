// Tạo RIÊNG 1 slide "07 / Kiến trúc hệ thống" — sơ đồ khối, ưu tiên HÌNH, chữ tối
// thiểu (logo + tên + 2-3 chữ mô tả), theo đúng dạng bản dựng tay ngoài Canva.
//
//   node presentation/generate_architecture_slide.js
//   -> presentation/07_kien_truc_slide.pptx
//
// File riêng thay vì sửa generate_pitch_deck.js: lý do như đầu generate_eval_slide.js
// (dựng đủ deck rồi cắt mảng slide nội bộ làm file pptx hỏng).
//
// Sơ đồ cũ sai 3 chỗ so với code, đã sửa:
//   1. Thiếu ocr-service (PaddleOCR + VietOCR trên Modal) — ocr-service/modal_app.py,
//      src/api/routes.py::scan_prescription.
//   2. PostgreSQL không nằm trong Docker và là HAI DB: Supabase + CockroachDB —
//      src/db/session.py (hai engine tách rời).
//   3. DeepSeek không nối vào LangGraph: không node nào của graph gọi LLM
//      (explain_node.py chỉ pass-through). Lệnh gọi LLM nằm ở rollup_explain.py /
//      food_disease_explain.py, do routes.py gọi SAU khi agent chạy xong.
//
// Logo trong presentation/logos/ (Simple Icons, đã rasterize sang PNG). Thiếu file
// nào thì khối đó tự lùi về chỉ có chữ, script vẫn chạy.

const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Team MediCheck — VMEC-12';
pptx.subject = 'Kiến trúc hệ thống MediCheck';
pptx.title = 'MediCheck — Kiến trúc hệ thống';
pptx.company = 'AI20K Build Phase — Cohort 3';
pptx.lang = 'vi-VN';
pptx.theme = { headFontFace: 'Montserrat', bodyFontFace: 'Montserrat', lang: 'vi-VN' };
pptx.defineSlideMaster({
  title: 'MEDICHECK',
  background: { color: 'FFFFFF' },
  objects: [
    { rect: { x: 0, y: 0, w: 13.333, h: 0.06, fill: { color: '4D73C9' }, line: { color: '4D73C9' } } },
    { text: { text: 'MEDICHECK  /  VMEC-12', options: { x: 0.55, y: 7.12, w: 3.0, h: 0.18, fontFace: 'Montserrat', fontSize: 7.5, bold: true, color: '73829E', charSpacing: 1.4, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.08, w: 0.55, h: 0.22, color: '73829E', fontFace: 'Montserrat', fontSize: 8, align: 'right', margin: 0 },
});

const C = {
  navy: '11284C',
  blue: '2F5BD0',
  blue2: '7899E8',
  white: 'FFFFFF',
  text: '253B5F',
  muted: '667792',
  line: 'C3D3EE',
  soft: 'DCE6F8',
};

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: 'Montserrat',
    fontSize: opts.fontSize || 12,
    color: opts.color || C.text,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || 'center',
    valign: opts.valign || 'mid',
    margin: 0,
    breakLine: false,
    fit: 'shrink',
    lineSpacingMultiple: opts.lineSpacingMultiple || 1.0,
    charSpacing: opts.charSpacing,
    isTextBox: true,
  });
}

function rect(slide, x, y, w, h, fill, radius = 0.12, lineColor = fill, dash = 'solid', lineWidth = 1) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: radius,
    fill: fill ? { color: fill } : { type: 'none' },
    line: { color: lineColor, width: lineColor === fill ? 0 : lineWidth, dashType: dash },
  });
}

function arrow(slide, x1, y1, x2, y2, color = C.blue2, width = 1.5, both = false) {
  slide.addShape(pptx.ShapeType.line, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    line: {
      color, width,
      beginArrowType: both || x2 < x1 || y2 < y1 ? 'triangle' : 'none',
      endArrowType: both || (x2 >= x1 && y2 >= y1) ? 'triangle' : 'none',
    },
  });
}

// Đọc kích thước PNG từ IHDR để giữ đúng tỉ lệ logo (không cần thêm thư viện).
function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString('ascii', 1, 4) !== 'PNG') throw new Error(`Không phải PNG: ${file}`);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// Logo canh giữa theo chiều ngang của (cx), cao đúng h.
function logo(slide, name, cx, y, h) {
  const file = path.join(__dirname, 'logos', `${name}.png`);
  if (!fs.existsSync(file)) return 0;
  const s = pngSize(file);
  const w = (s.w / s.h) * h;
  slide.addImage({ path: file, x: cx - w / 2, y, w, h });
  return w;
}

// Khung lớn: viền mảnh, nhãn nằm đè lên cạnh trên (đúng kiểu bản Canva).
function frame(slide, x, y, w, h, label, pillW) {
  rect(slide, x, y, w, h, C.white, 0.14, C.line, 'solid', 1.25);
  const px = x + (w - pillW) / 2;
  rect(slide, px, y - 0.16, pillW, 0.32, C.navy, 0.16);
  addText(slide, label, px + 0.05, y - 0.15, pillW - 0.1, 0.3, { fontSize: 8, bold: true, color: C.white, charSpacing: 0.7 });
}

// Khối: logo ở trên, tên đậm, 1 dòng mô tả rất ngắn — tất cả canh giữa, xếp dọc và
// căn giữa theo chiều cao của khối.
function card(slide, x, y, w, h, icon, name, caption, iconH = 0.34) {
  rect(slide, x, y, w, h, C.white, 0.11, C.soft, 'solid', 1.25);
  const cx = x + w / 2;
  const nameH = name ? 0.24 : 0;
  const capH = caption ? 0.18 : 0;
  const total = (icon ? iconH + 0.06 : 0) + nameH + capH;
  let cy = y + (h - total) / 2;
  if (icon) cy += logo(slide, icon, cx, cy, iconH) ? iconH + 0.06 : 0;
  if (name) {
    addText(slide, name, x + 0.06, cy, w - 0.12, nameH, { fontSize: 12.5, bold: true, color: C.navy });
    cy += nameH;
  }
  if (caption) addText(slide, caption, x + 0.06, cy, w - 0.12, capH, { fontSize: 8.2, color: C.muted });
}

// Nhãn nhỏ nằm ĐÈ lên đường nối (đường vẽ xuyên qua, chỉ hở hai đầu mũi tên).
function chip(slide, cx, cy, w, h, text) {
  rect(slide, cx - w / 2, cy - h / 2, w, h, C.white, 0.09, C.line, 'solid', 1);
  addText(slide, text, cx - w / 2 + 0.04, cy - h / 2, w - 0.08, h, { fontSize: 7, color: C.text, lineSpacingMultiple: 1.1 });
}

// ---- Slide ----
const slide = pptx.addSlide('MEDICHECK');
addText(slide, '07 / KIẾN TRÚC HỆ THỐNG', 0.58, 0.30, 6.0, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.8, align: 'left' });
addText(slide, 'Kiến trúc phân lớp, tách rõ trải nghiệm - nghiệp vụ - AI - dữ liệu', 0.58, 0.66, 12.2, 0.6, { fontSize: 24, bold: true, color: C.navy, align: 'left' });

// ---------- CLIENT ----------
frame(slide, 0.60, 2.30, 2.30, 2.20, 'CLIENT', 1.05);
card(slide, 0.88, 2.72, 1.74, 1.18, 'nextdotjs', null, null, 0.62);
addText(slide, 'Giao diện Next.js', 0.70, 4.02, 2.10, 0.24, { fontSize: 8.6, color: C.muted });

// Client <-> Server
arrow(slide, 2.90, 2.96, 3.85, 2.96, C.blue2, 1.5);
arrow(slide, 3.85, 3.28, 2.90, 3.28, C.blue2, 1.5);
chip(slide, 3.375, 3.12, 0.86, 0.80, 'Gửi yêu cầu /\nNhận kết quả\nqua REST API');

// ---------- SERVER ----------
frame(slide, 3.85, 1.55, 4.30, 4.90, 'SERVER', 1.15);
rect(slide, 4.05, 2.00, 3.90, 4.30, null, 0.14, C.blue2, 'dash', 1.25);
const dockerW = logo(slide, 'docker', 5.72, 2.10, 0.26);
addText(slide, 'docker', 5.80 + dockerW / 2, 2.12, 0.9, 0.22, { fontSize: 11, bold: true, color: '2496ED', align: 'left' });

card(slide, 4.30, 2.50, 3.40, 0.92, 'fastapi', 'FastAPI', 'Backend API');
arrow(slide, 6.00, 3.42, 6.00, 3.62, C.blue2, 1.5);
card(slide, 4.30, 3.62, 3.40, 0.58, null, 'Khởi chạy quy trình phân tích', null);
arrow(slide, 6.00, 4.20, 6.00, 4.40, C.blue2, 1.5);
card(slide, 4.30, 4.40, 3.40, 0.92, 'langgraph', 'LangGraph', 'AI Agent');
arrow(slide, 6.00, 5.32, 6.00, 5.52, C.blue2, 1.5);
card(slide, 4.30, 5.52, 3.40, 0.68, null, 'Tổng hợp giải thích', 'Nơi duy nhất gọi LLM');
const renderW = logo(slide, 'render', 7.30, 6.36, 0.14);
addText(slide, 'Render', 7.40 + renderW / 2, 6.35, 0.6, 0.18, { fontSize: 8, bold: true, color: C.muted, align: 'left' });

// ---------- Đường nối sang phải ----------
arrow(slide, 8.15, 2.96, 8.95, 2.96, C.blue2, 1.5, true);
arrow(slide, 8.15, 4.86, 8.95, 4.86, C.blue2, 1.5, true);
arrow(slide, 8.15, 5.86, 8.95, 5.86, C.blue2, 1.5, true);

// ---------- OCR ----------
frame(slide, 8.95, 2.25, 3.90, 1.40, 'DỊCH VỤ OCR', 1.45);
card(slide, 9.15, 2.62, 3.50, 0.88, 'modal', 'OCR đơn thuốc', 'PaddleOCR + VietOCR');
chip(slide, 8.55, 2.96, 0.76, 0.56, 'Quét ảnh\nđơn thuốc');

// ---------- CƠ SỞ DỮ LIỆU ----------
frame(slide, 8.95, 3.85, 3.90, 1.55, 'CƠ SỞ DỮ LIỆU', 1.55);
card(slide, 9.15, 4.25, 1.68, 1.02, 'supabase', 'Supabase', 'Hồ sơ, lịch sử', 0.30);
card(slide, 10.97, 4.25, 1.68, 1.02, 'cockroachlabs', 'CockroachDB', 'Dữ liệu DDInter', 0.30);
chip(slide, 8.55, 4.86, 0.76, 0.56, 'Tra cứu tương tác\nvà lưu kết quả');

// ---------- DỊCH VỤ AI ----------
frame(slide, 8.95, 5.60, 3.90, 1.25, 'DỊCH VỤ AI', 1.25);
card(slide, 9.15, 5.85, 3.50, 0.85, 'deepseek', 'DeepSeek Chat API', null, 0.40);
chip(slide, 8.55, 5.86, 0.76, 0.50, 'Dịch và tổng hợp\ngiải thích');

if (typeof slide.addNotes === 'function') {
  slide.addNotes([
    'Ba điều muốn người nghe nhớ ở slide này.',
    'Thứ nhất là ranh giới giữa dữ liệu và mô hình sinh. Agent LangGraph năm node không hề gọi LLM: nó chuẩn hoá tên thuốc, tra DDInter bằng SQL, xếp hạng mức độ rồi hậu kiểm ngôn từ bằng quy tắc. LLM chỉ được gọi ở khối tổng hợp giải thích phía sau, để viết lại thành đoạn tiếng Việt dễ đọc. Nhờ vậy mô hình có sai thì sai ở cách diễn đạt, không sai ở dữ kiện tương tác.',
    'Thứ hai, hệ thống dùng hai cơ sở dữ liệu Postgres quản trị sẵn trên cloud chứ không phải một Postgres đóng trong Docker: Supabase giữ dữ liệu người dùng và lịch sử, CockroachDB giữ riêng ba bảng dữ kiện DDInter vốn chiếm hơn chín mươi lăm phần trăm dung lượng.',
    'Thứ ba, nhận dạng đơn thuốc là một service tách hẳn, chạy PaddleOCR kết hợp VietOCR trên Modal theo dạng serverless, backend chỉ gọi sang qua proxy có xác thực. Tách ra vì image OCR nặng khoảng bốn gigabyte, để chung sẽ kéo nặng toàn bộ backend.',
    'Về xác thực: không phải JWT như sơ đồ cũ ghi, mà là token tự ký HMAC đặt trong cookie HttpOnly kèm CSRF.',
  ].join(' '));
}

const out = path.join(__dirname, '07_kien_truc_slide.pptx');
pptx.writeFile({ fileName: out, compression: true })
  .then(() => console.log(`Created: ${out}`))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
