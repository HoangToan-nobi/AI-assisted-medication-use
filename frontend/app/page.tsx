"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login, register } from "@/lib/api";
import { saveSession } from "@/lib/auth";

type Mode = "login" | "register";
type Role = "patient" | "pharmacist";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<Role>("patient");
  const [hoTen, setHoTen] = useState("");
  const [email, setEmail] = useState("");
  const [matKhau, setMatKhau] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const auth =
        mode === "login"
          ? await login(email, matKhau)
          : await register(hoTen, email, matKhau, role);
      saveSession({
        accessToken: auth.access_token,
        userId: auth.user_id,
        hoTen: auth.ho_ten,
        vaiTro: auth.vai_tro,
      });
      router.push(auth.vai_tro === "patient" ? "/dashboard" : "/patients");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Có lỗi xảy ra, vui lòng thử lại.");
    } finally {
      setLoading(false);
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
                    🧑 Bệnh nhân
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
      </div>
    </div>
  );
}
