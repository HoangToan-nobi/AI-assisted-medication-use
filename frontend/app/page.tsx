"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import BrandLogo from "@/components/BrandLogo";
import MaterialIcon from "@/components/MaterialIcon";
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
  const [showPassword, setShowPassword] = useState(false);
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

  const isPharmacist = role === "pharmacist";

  return (
    <div className="auth-shell">
      <BrandLogo size="lg" showTagline />

      <div className="auth-card">
        <h2 className="auth-card__heading">
          {mode === "login"
            ? isPharmacist
              ? "Đăng nhập Dược sĩ"
              : "Đăng nhập Bệnh nhân"
            : "Đăng ký tài khoản"}
        </h2>

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
                <div className="input-field input-field--no-icon">
                  <input
                    id="ho_ten"
                    required
                    value={hoTen}
                    onChange={(e) => setHoTen(e.target.value)}
                    placeholder="Nguyễn Văn A"
                  />
                </div>
              </div>
              <div className="field">
                <label>Vai trò</label>
                <div className="role-tabs">
                  <button
                    type="button"
                    className={role === "patient" ? "active" : ""}
                    onClick={() => setRole("patient")}
                  >
                    Bệnh nhân
                  </button>
                  <button
                    type="button"
                    className={role === "pharmacist" ? "active" : ""}
                    onClick={() => setRole("pharmacist")}
                  >
                    Dược sĩ
                  </button>
                </div>
              </div>
            </>
          )}

          {mode === "login" && (
            <div className="field">
              <label htmlFor="role_display">Vai trò</label>
              <div className="input-field input-field--no-icon">
                <input
                  id="role_display"
                  readOnly
                  value={isPharmacist ? "Dược sĩ" : "Bệnh nhân"}
                />
              </div>
            </div>
          )}

          <div className="field">
            <label htmlFor="email">Email của bạn</label>
            <div className="input-field">
              <MaterialIcon name="mail" size={20} className="input-field__icon" />
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ban@vidu.com"
              />
            </div>
          </div>

          <div className="field">
            <div className="input-field__label-row">
              <label htmlFor="mat_khau">Mật khẩu</label>
              {mode === "login" && (
                <a href="#" onClick={(e) => e.preventDefault()}>
                  Quên mật khẩu?
                </a>
              )}
            </div>
            <div className="input-field">
              <MaterialIcon name="lock" size={20} className="input-field__icon" />
              <input
                id="mat_khau"
                type={showPassword ? "text" : "password"}
                required
                minLength={6}
                value={matKhau}
                onChange={(e) => setMatKhau(e.target.value)}
                placeholder="Tối thiểu 6 ký tự"
              />
              <button
                type="button"
                className="input-field__action"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                <MaterialIcon name={showPassword ? "visibility_off" : "visibility"} size={20} />
              </button>
            </div>
          </div>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" disabled={loading} className="btn-block">
            {loading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Đang xử lý...
              </>
            ) : (
              <>
                {mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
                <MaterialIcon name="arrow_forward" size={20} />
              </>
            )}
          </button>
        </form>

        {mode === "login" && (
          <div className="auth-role-switch">
            <span>{isPharmacist ? "Bạn là bệnh nhân?" : "Bạn là nhân viên y tế?"}</span>
            <button type="button" onClick={() => setRole(isPharmacist ? "patient" : "pharmacist")}>
              <MaterialIcon name="medical_services" size={18} />
              {isPharmacist ? "Chuyển sang vai trò Bệnh nhân" : "Chuyển sang vai trò Dược sĩ"}
            </button>
          </div>
        )}

        {mode === "login" ? (
          <p className="auth-footer">
            Chưa có tài khoản?{" "}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setMode("register");
              }}
            >
              Đăng ký ngay
            </a>
          </p>
        ) : (
          <p className="auth-footer">
            Đã có tài khoản?{" "}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setMode("login");
              }}
            >
              Đăng nhập
            </a>
          </p>
        )}
      </div>
      <Link className="guest-entry-link" href="/interaction">Tiếp tục với tư cách khách <MaterialIcon name="arrow_forward" size={17} /></Link>
    </div>
  );
}
