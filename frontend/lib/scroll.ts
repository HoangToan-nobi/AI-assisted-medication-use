const STICKY_HEADER_SELECTOR = ".patient-header, .pharmacist-nav";
const EXTRA_GAP_PX = 28;

// Cuộn mượt tới `elementId`, chừa đúng chiều cao header sticky (đo trực tiếp
// bằng getBoundingClientRect ngay lúc cuộn) thay vì đoán một con số cố định
// bằng CSS scroll-margin-top - cách cũ từng bị hụt vì không khớp chiều cao
// header thực tế trên trình duyệt người dùng.
export function scrollBelowStickyHeader(elementId: string) {
  const target = document.getElementById(elementId);
  if (!target) return;
  const header = document.querySelector(STICKY_HEADER_SELECTOR);
  const headerHeight = header instanceof HTMLElement ? header.getBoundingClientRect().height : 0;
  const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - EXTRA_GAP_PX;
  window.scrollTo({ top: Math.max(top, 0), behavior: "smooth" });
}
