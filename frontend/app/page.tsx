"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login, register } from "@/lib/api";
import { saveSession } from "@/lib/auth";

type Mode = "login" | "register";
type Role = "patient" | "pharmacist";

// Tài khoản demo - tạo sẵn bằng `python scripts/seed_demo_users.py` (bệnh nhân đã có
// sẵn thuốc, dược sĩ đã được gán phụ trách). CHỈ để demo/dev nội bộ.
const DEMO_LOGIN_ENABLED = process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN !== "false";
const DEMO_ACCOUNTS: Record<Role, { email: string; matKhau: string; label: string; icon: string }> = {
  patient: {
    email: "demo-patient@medguard.local",
    matKhau: "demo1234",
    label: "Vào với vai trò Người dùng",
    icon: "🧑",
  },
  pharmacist: {
    email: "demo-pharmacist@medguard.local",
    matKhau: "demo1234",
    label: "Vào với vai trò Dược sĩ",
    icon: "💊",
  },
};

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<Role>("patient");
  const [hoTen, setHoTen] = useState("");
  const [email, setEmail] = useState("");
  const [matKhau, setMatKhau] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoLoadingRole, setDemoLoadingRole] = useState<Role | null>(null);

  async function completeLogin(auth: Awaited<ReturnType<typeof login>>) {
    saveSession({
      accessToken: auth.access_token,
      userId: auth.user_id,
      hoTen: auth.ho_ten,
      vaiTro: auth.vai_tro,
    });
    router.push(auth.vai_tro === "patient" ? "/dashboard" : "/patients");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const auth =
        mode === "login"
          ? await login(email, matKhau)
          : await register(hoTen, email, matKhau, role);
      await completeLogin(auth);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Có lỗi xảy ra, vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDemoLogin(demoRole: Role) {
    setError(null);
    setDemoLoadingRole(demoRole);
    try {
      const { email: demoEmail, matKhau: demoMatKhau } = DEMO_ACCOUNTS[demoRole];
      const auth = await login(demoEmail, demoMatKhau);
      await completeLogin(auth);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Chưa có tài khoản demo — chạy "python scripts/seed_demo_users.py" trước (${err.message}).`
          : "Có lỗi xảy ra, vui lòng thử lại."
      );
    } finally {
      setDemoLoadingRole(null);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-header">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true">
              🛡️
            </span>
            MedGuard AI
          </span>
          <p>Trợ lý AI kiểm tra tương tác thuốc an toàn</p>
        </div>

        <div className="role-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            Đăng ký
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <>
              <div className="field">
                <label htmlFor="ho_ten">Họ tên</label>
                <input
                  id="ho_ten"
                  required
                  value={hoTen}
                  onChange={(e) => setHoTen(e.target.value)}
                  placeholder="Nguyễn Văn A"
                />
              </div>
              <div className="field">
                <label>Vai trò</label>
                <div className="role-tabs">
                  <button
                    type="button"
                    className={role === "patient" ? "active" : ""}
                    onClick={() => setRole("patient")}
                  >
                    🧑 Người dùng
                  </button>
                  <button
                    type="button"
                    className={role === "pharmacist" ? "active" : ""}
                    onClick={() => setRole("pharmacist")}
                  >
                    💊 Dược sĩ
                  </button>
                </div>
              </div>
            </>
          )}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@vidu.com"
            />
          </div>
          <div className="field">
            <label htmlFor="mat_khau">Mật khẩu</label>
            <input
              id="mat_khau"
              type="password"
              required
              minLength={6}
              value={matKhau}
              onChange={(e) => setMatKhau(e.target.value)}
              placeholder="Tối thiểu 6 ký tự"
            />
          </div>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" disabled={loading} style={{ width: "100%", marginTop: 8 }}>
            {loading && <span className="spinner" aria-hidden="true" />}
            {loading ? "Đang xử lý..." : mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
        </form>

        {DEMO_LOGIN_ENABLED && mode === "login" && (
          <>
            <div className="auth-divider">
              <span>hoặc dùng thử ngay</span>
            </div>
            <div className="field" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {(Object.keys(DEMO_ACCOUNTS) as Role[]).map((demoRole) => (
                <button
                  key={demoRole}
                  type="button"
                  className="secondary"
                  style={{ width: "100%" }}
                  disabled={demoLoadingRole !== null}
                  onClick={() => handleDemoLogin(demoRole)}
                >
                  {demoLoadingRole === demoRole ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span aria-hidden="true">{DEMO_ACCOUNTS[demoRole].icon}</span>
                  )}
                  {DEMO_ACCOUNTS[demoRole].label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
