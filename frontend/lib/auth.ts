export type Role = "patient" | "pharmacist";

export type Session = {
  accessToken: string;
  userId: string;
  hoTen: string;
  vaiTro: Role;
};

const STORAGE_KEY = "medguard_session";
const SESSION_UPDATED_EVENT = "medguard_session_updated";

export function saveSession(session: Session): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  // Layout (header) doc session 1 lan luc mount va giu trong state rieng, khong
  // tu remount khi chuyen trang (Next.js App Router giu layout song xuyen route) -
  // phat event de layout dang mo cap nhat lai ngay, khong can F5.
  window.dispatchEvent(new Event(SESSION_UPDATED_EVENT));
}

export function onSessionUpdated(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(SESSION_UPDATED_EVENT, callback);
  return () => window.removeEventListener(SESSION_UPDATED_EVENT, callback);
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}
