"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { listPatientNotifications, markNotificationRead, type NotificationItem } from "@/lib/api";
import { formatVietnameseDateTime } from "@/lib/datetime";

type NotificationBellProps = {
  patientId: string;
  token: string;
};

// Chuông thông báo ở header - liệt kê TOÀN BỘ thông báo (đã đọc lẫn chưa đọc) mới
// nhất trước, chưa đọc thì in đậm + chấm xanh. Bấm 1 thông báo -> đánh dấu đã đọc
// rồi điều hướng tới kết quả lần kiểm tra liên quan (nếu có).
export default function NotificationBell({ patientId, token }: NotificationBellProps) {
  const router = useRouter();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Chuông sống trong layout - mount 1 lần duy nhất cho cả phiên, không remount mỗi
  // khi chuyển trang như các page component (VD dashboard) - nên phải TỰ làm mới
  // định kỳ + mỗi lần mở panel, chứ không thể chỉ fetch 1 lần lúc mount như trước
  // (khi đó thông báo mới từ dược sĩ xác nhận sẽ không hiện cho tới khi tải lại cả trang).
  useEffect(() => {
    let cancelled = false;
    function refresh() {
      listPatientNotifications(patientId, token).then((data) => { if (!cancelled) setNotifications(data); }).catch(() => undefined);
    }
    refresh();
    const interval = window.setInterval(refresh, 30000);
    function handleVisibility() {
      if (document.visibilityState === "visible") refresh();
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [patientId, token]);

  useEffect(() => {
    if (!open) return;
    listPatientNotifications(patientId, token).then(setNotifications).catch(() => undefined);
    function handleClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const unreadCount = notifications.filter((n) => !n.da_doc).length;

  async function handleClickNotification(n: NotificationItem) {
    if (!n.da_doc) {
      try {
        await markNotificationRead(patientId, n.id, token);
        setNotifications((prev) => prev.map((item) => (item.id === n.id ? { ...item, da_doc: true } : item)));
      } catch { /* vẫn điều hướng dù lỡ đánh dấu đã đọc thất bại */ }
    }
    setOpen(false);
    if (n.interaction_check_id) router.push(`/check-result?checkId=${n.interaction_check_id}`);
  }

  return (
    <div className="notification-bell" ref={panelRef}>
      <button type="button" className="icon-btn" onClick={() => setOpen((v) => !v)} aria-label="Thông báo" title="Thông báo">
        <MaterialIcon name="notifications" size={20} />
        {unreadCount > 0 && <span className="notification-bell__badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
      </button>
      {open && (
        <div className="notification-bell__panel">
          <p className="notification-bell__title">Thông báo</p>
          {notifications.length === 0 ? (
            <p className="notification-bell__empty">Chưa có thông báo nào.</p>
          ) : (
            <ul className="notification-bell__list">
              {notifications.map((n) => (
                <li key={n.id} className={n.da_doc ? "" : "notification-bell__item--unread"} onClick={() => void handleClickNotification(n)}>
                  {!n.da_doc && <span className="notification-bell__dot" />}
                  <div>
                    <p>{n.noi_dung}</p>
                    <small>{formatVietnameseDateTime(n.thoi_gian_tao)}</small>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
