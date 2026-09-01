// Tạo RIÊNG 1 slide "01 / Bài toán — Khảo sát người dùng".
//
// Cùng cách làm với generate_eval_slide.js: chỉ thêm đúng 1 slide ngay từ đầu nên file
// .pptx sinh ra nhất quán, mở/import (PowerPoint, WPS, Canva, Google Slides) bình thường.
//
//   node presentation/generate_survey_slide.js
//   -> presentation/01_khao_sat_nguoi_dung_slide.pptx
//
// Hai biểu đồ được VẼ LẠI bằng shape (không chèn ảnh chụp Google Form) để font/màu khớp
// hệ thiết kế của generate_pitch_deck.js và vẫn chỉnh sửa được trong PowerPoint.

const pptxgen = require('pptxgenjs');
const path = require('path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Team MediCheck — VMEC-12';
pptx.subject = 'Khảo sát nhu cầu người dùng';
pptx.title = 'MediCheck — Khảo sát người dùng';
pptx.company = 'AI20K Build Phase — Cohort 3';
pptx.lang = 'vi-VN';
pptx.theme = {
  headFontFace: 'Montserrat',
  bodyFontFace: 'Montserrat',
  lang: 'vi-VN',
};
pptx.defineSlideMaster({
  title: 'MEDICHECK',
  background: { color: 'F5F8FD' },
  objects: [
    { rect: { x: 0, y: 0, w: 13.333, h: 0.06, fill: { color: '4D73C9' }, line: { color: '4D73C9' } } },
    { text: { text: 'MEDICHECK  /  VMEC-12', options: { x: 0.55, y: 7.12, w: 3.0, h: 0.18, fontFace: 'Montserrat', fontSize: 7.5, bold: true, color: '73829E', charSpacing: 1.4, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.08, w: 0.55, h: 0.22, color: '73829E', fontFace: 'Montserrat', fontSize: 8, align: 'right', margin: 0 },
});

const C = {
  navy: '11284C',
  blue: '4D73C9',
  blueSoft: 'A9C0EA',
  pale: 'E9F0FF',
  white: 'FFFFFF',
  text: '253B5F',
  muted: '667792',
  green: '2C9A83',
  greenPale: 'E1F5EF',
  amber: 'C68A2E',
  amberPale: 'FFF1D9',
  line: 'CBD8ED',
};

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: opts.fontFace || 'Montserrat',
    fontSize: opts.fontSize || 18,
    color: opts.color || C.text,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || 'left',
    valign: opts.valign || 'mid',
    margin: opts.margin === undefined ? 0 : opts.margin,
    breakLine: false,
    fit: 'shrink',
    lineSpacingMultiple: opts.lineSpacingMultiple || 1.0,
    charSpacing: opts.charSpacing,
    isTextBox: true,
  });
}

function rect(slide, x, y, w, h, fill, radius = 0.16, line = fill) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: radius,
    fill: { color: fill },
    line: { color: line, width: line === fill ? 0 : 1 },
  });
}

function bar(slide, x, y, w, h, fill) {
  slide.addShape(pptx.ShapeType.rect, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 } });
}

function title(slide, kicker, heading, subtitle) {
  addText(slide, kicker.toUpperCase(), 0.58, 0.34, 6.5, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.8 });
  addText(slide, heading, 0.58, 0.70, 12.2, 0.62, { fontSize: 24, bold: true, color: C.navy });
  if (subtitle) addText(slide, subtitle, 0.58, 1.31, 12.2, 0.42, { fontSize: 12.5, color: C.muted });
}

// ---- Biểu đồ cột: vẽ tay để khớp font/màu của deck ----
// values: mảng 5 số (mức 1..5). highlightFrom: từ mức nào trở lên thì tô đậm.
function columnChart(slide, x, y, w, h, values, total, highlightFrom) {
  const MAX = 26;               // thang đo chung cho cả hai biểu đồ để so sánh được
  const base = y + h;           // đường 0
  const plotX = x + 0.42;       // chừa chỗ cho nhãn trục dọc
  const plotW = w - 0.42;
  const slot = plotW / values.length;
  const barW = Math.min(0.72, slot * 0.62);

  [0, 10, 20].forEach((tick) => {
    const gy = base - (tick / MAX) * h;
    bar(slide, plotX, gy, plotW, 0.01, tick === 0 ? C.line : 'E4EBF7');
    addText(slide, String(tick), x, gy - 0.11, 0.34, 0.22, { fontSize: 7.5, color: C.muted, align: 'right' });
  });

  values.forEach((v, i) => {
    const bh = (v / MAX) * h;
    const bx = plotX + i * slot + (slot - barW) / 2;
    const by = base - bh;
    const strong = i + 1 >= highlightFrom;
    bar(slide, bx, by, barW, bh, strong ? C.blue : C.blueSoft);
    const pct = ((v / total) * 100).toFixed(1).replace('.', ',');
    addText(slide, v + ' · ' + pct + '%', bx - 0.34, by - 0.24, barW + 0.68, 0.22,
      { fontSize: 8, bold: true, color: strong ? C.navy : C.muted, align: 'center' });
    addText(slide, String(i + 1), bx - 0.2, base + 0.05, barW + 0.4, 0.22,
      { fontSize: 9.5, bold: true, color: C.text, align: 'center' });
  });
}

function surveyCard(slide, x, y, w, h, question, values, total, highlightFrom, anchorLow, anchorHigh) {
  rect(slide, x, y, w, h, C.white, 0.18, C.line);
  slide.addShape(pptx.ShapeType.rect, { x, y, w: 0.08, h, fill: { color: C.blue }, line: { color: C.blue, width: 0 } });
  addText(slide, question, x + 0.34, y + 0.22, w - 0.62, 0.52, { fontSize: 12.5, bold: true, color: C.navy, valign: 'top', lineSpacingMultiple: 1.05 });
  addText(slide, total + ' câu trả lời  ·  thang 1–5', x + 0.34, y + 0.80, w - 0.62, 0.22, { fontSize: 8.6, color: C.muted, charSpacing: 0.6 });
  columnChart(slide, x + 0.34, y + 1.10, w - 0.68, 1.72, values, total, highlightFrom);
  addText(slide, anchorLow, x + 0.76, y + h - 0.32, 2.4, 0.22, { fontSize: 8, italic: true, color: C.muted });
  addText(slide, anchorHigh, x + w - 3.16, y + h - 0.32, 2.4, 0.22, { fontSize: 8, italic: true, color: C.muted, align: 'right' });
}

function takeaway(slide, x, y, w, h, stat, label, note, accent, accentPale) {
  rect(slide, x, y, w, h, accentPale, 0.16);
  addText(slide, stat, x + 0.26, y + 0.12, 1.55, 0.44, { fontSize: 19, bold: true, color: accent });
  addText(slide, label, x + 1.85, y + 0.11, w - 2.15, 0.28, { fontSize: 10.5, bold: true, color: C.navy });
  addText(slide, note, x + 1.85, y + 0.40, w - 2.15, 0.30, { fontSize: 9.2, color: C.muted, valign: 'top' });
}

// ---- Slide: 01 / Bài toán — Khảo sát người dùng ----
const slide = pptx.addSlide('MEDICHECK');
title(
  slide,
  '01 / Bài toán  ·  Khảo sát người dùng',
  'Người dùng có thực sự cần một nơi để tra cứu tương tác thuốc?',
  'Khảo sát online 54 người trước khi xây sản phẩm — kiểm chứng nhu cầu bằng dữ liệu, không phải bằng giả định của nhóm.'
);

const CARD_Y = 1.88;
const CARD_H = 3.30;
const CARD_W = 5.98;

surveyCard(
  slide, 0.58, CARD_Y, CARD_W, CARD_H,
  'Bạn lo ngại về tương tác khi dùng nhiều thuốc ở mức nào?',
  [5, 8, 22, 13, 6], 54, 3,
  '1 · Không lo', 'Rất lo · 5'
);

surveyCard(
  slide, 6.77, CARD_Y, CARD_W, CARD_H,
  'Bạn sẵn sàng dùng nền tảng tra cứu tương tác trước khi dùng nhiều thuốc ở mức nào?',
  [6, 5, 19, 9, 15], 54, 3,
  '1 · Không dùng', 'Chắc chắn dùng · 5'
);

const T_Y = 5.34;
takeaway(
  slide, 0.58, T_Y, CARD_W, 0.80,
  '75,9%', 'chọn mức 3–5 về mức độ lo ngại',
  'Lo về tương tác thuốc là mối quan tâm phổ biến, không phải nhu cầu ngách.',
  C.amber, C.amberPale
);
takeaway(
  slide, 6.77, T_Y, CARD_W, 0.80,
  '79,6%', 'sẵn sàng tra cứu trước khi uống thuốc',
  '27,8% chọn thẳng mức 5 — không ngại thêm một bước nếu bước đó đủ nhanh.',
  C.green, C.greenPale
);

addText(slide, 'Mẫu thuận tiện, cỡ nhỏ (n = 54) — dùng để định hướng sản phẩm, chưa đại diện cho dân số chung.',
  0.58, 6.24, 12.17, 0.24, { fontSize: 9, italic: true, color: C.muted });

rect(slide, 0.58, 6.54, 12.17, 0.46, C.navy, 0.14);
addText(slide, 'Người dùng đã lo sẵn — thứ họ thiếu là một chỗ tra cứu đủ tin cậy và đủ dễ hiểu để tự kiểm tra trước khi uống.',
  0.85, 6.60, 11.63, 0.34, { fontSize: 10.5, bold: true, color: C.white, align: 'center' });

if (typeof slide.addNotes === 'function') {
  slide.addNotes('Slide này trả lời câu hỏi "nhu cầu có thật không". Nhóm khảo sát 54 người trước khi bắt tay vào xây. Kết quả: 75,9% chọn mức 3 trở lên về mức độ lo ngại tương tác thuốc, và 79,6% chọn mức 3 trở lên về mức sẵn sàng dùng một nền tảng tra cứu trước khi uống — trong đó gần 28% chọn thẳng mức 5. Hai con số nói hai chuyện khác nhau: mối lo đã có sẵn, và người dùng không ngại thêm một bước tra cứu nếu bước đó đủ nhanh. Nhóm cũng nói rõ giới hạn: đây là mẫu thuận tiện, cỡ 54, dùng để định hướng sản phẩm chứ không phải bằng chứng dịch tễ — bằng chứng quy mô lớn nằm ở slide dữ liệu 1.700 đơn thuốc.');
}

const out = path.join(__dirname, '01_khao_sat_nguoi_dung_slide.pptx');
pptx.writeFile({ fileName: out, compression: true })
  .then(() => console.log('Created: ' + out))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
