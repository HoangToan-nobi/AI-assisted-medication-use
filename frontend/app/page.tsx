import Link from 'next/link';
import Image from 'next/image';

<<<<<<< HEAD
export default function LandingPage() {
  return (
    <div className="landing-shell">
      <header className="landing-container">
        <div className="landing-header">
          <div className="brand-logo" style={{ flexDirection: 'row', gap: '12px' }}>
            <span className="brand-logo__name" style={{ color: 'var(--primary-container)', fontSize: '24px' }}>MediCheck</span>
          </div>
          <nav className="landing-nav">
            <a href="#features" className="active">Features</a>
            <a href="#about">About Us</a>
            <a href="#services">Services</a>
            <a href="#pricing">Pricing</a>
          </nav>
          <div>
            <Link href="/auth" className="btn" style={{ borderRadius: '50px', padding: '10px 24px' }}>Sign In</Link>
          </div>
        </div>
      </header>
=======
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
>>>>>>> origin/main

      <main>
        <section className="landing-container landing-hero">
          <div className="landing-hero__content">
            <h1>MediCheck: Nền tảng kiểm tra tương tác thuốc thông minh</h1>
            <p>
              Bảo vệ sức khỏe của bạn bằng việc kiểm tra tương tác thuốc nhanh chóng và chính xác. 
              Giải pháp toàn diện cho bệnh nhân và chuyên gia y tế.
            </p>
            <div className="landing-hero__actions">
              <Link href="/auth" className="btn" style={{ borderRadius: '50px', padding: '16px 32px' }}>Bắt đầu ngay</Link>
              <a href="#features" className="btn secondary" style={{ borderRadius: '50px', padding: '16px 32px' }}>Tìm hiểu thêm</a>
            </div>
          </div>
          <div className="landing-hero__image">
            <Image src="/hero.png" alt="Pharmacist using tablet" width={600} height={400} priority />
          </div>
        </section>

<<<<<<< HEAD
        <section id="features" className="landing-features">
          <div className="landing-container">
            <h2>Tính năng nổi bật</h2>
            <div className="landing-features__grid">
              <div className="landing-feature-card">
                <div className="landing-feature-icon">
                  <span className="material-symbols-outlined">checklist</span>
                </div>
                <h3>Kiểm tra tương tác</h3>
                <p>Phân tích tương tác giữa các loại thuốc bạn đang dùng để đảm bảo an toàn tối đa.</p>
              </div>
              <div className="landing-feature-card">
                <div className="landing-feature-icon">
                  <span className="material-symbols-outlined">search</span>
                </div>
                <h3>Tra cứu thuốc</h3>
                <p>Thông tin chi tiết về hàng ngàn loại thuốc, liều lượng và tác dụng phụ.</p>
              </div>
              <div className="landing-feature-card">
                <div className="landing-feature-icon">
                  <span className="material-symbols-outlined">medical_information</span>
                </div>
                <h3>Hỗ trợ chuyên gia</h3>
                <p>Kết nối trực tiếp với dược sĩ và bác sĩ để nhận tư vấn chuyên môn.</p>
              </div>
            </div>
          </div>
        </section>
=======
      <div className="auth-card">
        <h2 className="auth-card__heading">
          {mode === "login"
            ? isPharmacist
              ? "Đăng nhập Dược sĩ"
              : "Đăng nhập Bệnh nhân"
            : "Đăng ký tài khoản"}
        </h2>
>>>>>>> origin/main

        <section id="about" className="landing-container landing-mission">
          <div className="landing-mission__image">
            <Image src="/mission.png" alt="Modern healthcare technology dashboard" width={600} height={400} />
          </div>
          <div className="landing-mission__content">
            <h2>Sứ mệnh của chúng tôi</h2>
            <p>
              Tại MediCheck, chúng tôi cam kết giảm thiểu sai sót y khoa và nâng cao an toàn 
              cho bệnh nhân tại Việt Nam. Bằng cách cung cấp công cụ kiểm tra tương tác thuốc 
              dễ sử dụng và đáng tin cậy, chúng tôi trao quyền cho cả người bệnh và chuyên gia 
              y tế trong việc đưa ra những quyết định điều trị an toàn nhất.
            </p>
          </div>
        </section>

        <section id="services" className="landing-audience">
          <div className="landing-container">
            <h2>Dành cho mọi đối tượng</h2>
            <div className="landing-audience__grid">
              <div className="landing-audience-card">
                <h3>
                  <span className="material-symbols-outlined">person</span>
                  Bệnh nhân
                </h3>
                <ul>
                  <li>Quản lý đơn thuốc cá nhân dễ dàng.</li>
                  <li>Nhận cảnh báo tức thì về tương tác thuốc nguy hiểm.</li>
                  <li>An tâm hơn trong quá trình điều trị tại nhà.</li>
                </ul>
              </div>
              <div className="landing-audience-card">
                <h3>
                  <span className="material-symbols-outlined">local_hospital</span>
                  Dược sĩ / Bác sĩ
                </h3>
                <ul>
                  <li>Công cụ tra cứu nhanh chóng tại phòng khám.</li>
                  <li>Cơ sở dữ liệu y khoa cập nhật liên tục.</li>
                  <li>Nâng cao chất lượng chăm sóc và tư vấn cho bệnh nhân.</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-cta">
          <div className="landing-container">
            <div className="landing-cta-inner">
              <h2>Sẵn sàng bảo vệ sức khỏe của bạn?</h2>
              <p>
                Đăng ký ngay hôm nay để trải nghiệm nền tảng kiểm tra tương tác thuốc 
                thông minh và an toàn nhất.
              </p>
              <Link href="/auth" className="btn">Đăng ký ngay</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="brand-logo" style={{ flexDirection: 'row', gap: '8px' }}>
            <span className="brand-logo__name" style={{ color: 'var(--primary-container)', fontSize: '20px' }}>MediCheck</span>
            <span style={{ marginLeft: '16px' }}>© 2024 MediCheck Healthcare Systems. All rights reserved.</span>
          </div>
          <div className="landing-footer-links">
            <Link href="#">Privacy Policy</Link>
            <Link href="#">Terms of Service</Link>
            <Link href="#">Cookie Policy</Link>
            <Link href="#">Contact Us</Link>
            <Link href="#">Support</Link>
          </div>
        </div>
<<<<<<< HEAD
      </footer>
=======

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
>>>>>>> origin/main
    </div>
  );
}
