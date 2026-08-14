"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, login, register } from "@/lib/api";
import { saveSession } from "@/lib/auth";
import MediFox from "@/components/MediFox";

type Mode = "login" | "register";
type Role = "patient" | "pharmacist";

const asset = (name: string) => encodeURI("/Bộ nhận diện y tế/" + name);

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<Role>("patient");
  const [hoTen, setHoTen] = useState("");
  const [email, setEmail] = useState("");
  const [matKhau, setMatKhau] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function changeMode(next: Mode) {
    setMode(next);
    setError(null);
  }

  async function finish(auth: Awaited<ReturnType<typeof login>>) {
    saveSession({
      accessToken: auth.access_token,
      userId: auth.user_id,
      hoTen: auth.ho_ten,
      vaiTro: auth.vai_tro,
    });
    router.push(
      auth.vai_tro === "patient" ? "/dashboard" : "/pharmacist-dashboard",
    );
  }

  async function demo(emailDemo: string) {
    setLoading(true);
    setError(null);
    try {
      await finish(await login(emailDemo, "demo1234"));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Không thể đăng nhập tài khoản demo.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth =
        mode === "login"
          ? await login(email, matKhau)
          : await register(hoTen, email, matKhau, role);
      await finish(auth);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Có lỗi xảy ra, vui lòng thử lại.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mc-auth">
      <style jsx global>{`
        .mc-auth {
          min-height: 100vh;
          background: #f7faff;
          color: #132a4d;
          font-family: Inter, Arial, sans-serif;
        }
        .mc-auth * {
          box-sizing: border-box;
        }
        .mc-auth__shell {
          width: min(1180px, calc(100% - 40px));
          margin: auto;
        }
        .mc-auth__header {
          height: 92px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .mc-auth__logo {
          position: relative;
          width: 142px;
          height: 44px;
          display: block;
        }
        .mc-auth__logo img {
          object-fit: contain;
          transform: none;
        }
        .mc-auth__back {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #4167b2;
          font-size: 13px;
          font-weight: 700;
          text-decoration: none;
        }
        .mc-auth__layout {
          position: relative;
          display: grid;
          grid-template-columns: 1fr minmax(400px, 500px);
          align-items: center;
          gap: 70px;
          min-height: calc(100vh - 150px);
          padding: 48px;
          border: 1px solid #d3e1f4;
          border-radius: 28px;
          background: linear-gradient(120deg, #fff, #edf4ff 58%, #fff);
          box-shadow: 0 24px 70px #365b8c16;
          overflow: hidden;
        }
        .mc-auth__layout:after {
          content: "";
          position: absolute;
          right: -12%;
          top: -28%;
          width: 58%;
          height: 135%;
          border-radius: 50%;
          background: #bcd5ff66;
          filter: blur(52px);
        }
        .mc-auth__intro,
        .mc-auth__card {
          position: relative;
          z-index: 1;
        }
        .mc-auth__eyebrow {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 22px;
          color: #4167b2;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.15em;
        }
        .mc-auth__eyebrow b {
          display: grid;
          place-items: center;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: #4167b2;
          color: #fff;
        }
        .mc-auth__intro h1 {
          margin: 0;
          font-size: clamp(42px, 5.3vw, 74px);
          font-weight: 600;
          letter-spacing: -0.06em;
          line-height: 0.96;
        }
        .mc-auth__intro h1 em {
          color: #5572bf;
          font-style: normal;
        }
        .mc-auth__intro p:not(.mc-auth__eyebrow) {
          max-width: 440px;
          margin: 24px 0;
          color: #5d6f88;
          font-size: 16px;
          line-height: 1.7;
        }
        .mc-auth__points {
          display: grid;
          gap: 13px;
          margin-top: 34px;
        }
        .mc-auth__point {
          display: flex;
          align-items: center;
          gap: 10px;
          color: #49607f;
          font-size: 13px;
        }
        .mc-auth__point .material-symbols-outlined {
          color: #4167b2;
        }
        .mc-auth__card {
          padding: 32px;
          border: 1px solid #c8d9f0;
          border-radius: 24px;
          background: #ffffffdf;
          box-shadow: 0 22px 45px #3057891b;
          backdrop-filter: blur(18px);
        }
        .mc-auth__tabs {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 4px;
          padding: 4px;
          border-radius: 14px;
          background: #eaf1fc;
        }
        .mc-auth__tab {
          border: 0;
          border-radius: 10px;
          padding: 11px;
          background: transparent;
          color: #6680a4;
          cursor: pointer;
          font: inherit;
          font-size: 13px;
          font-weight: 800;
        }
        .mc-auth__tab--active {
          background: #fff;
          color: #244b8d;
          box-shadow: 0 4px 12px #385b8b1c;
        }
        .mc-auth__title {
          margin: 27px 0 7px;
          font-size: 29px;
          letter-spacing: -0.04em;
        }
        .mc-auth__subtitle {
          margin: 0 0 23px;
          color: #657790;
          font-size: 14px;
        }
        .mc-auth__demo {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 9px;
          margin-bottom: 20px;
        }
        .mc-auth__demo button {
          border: 1px solid #c5d7f0;
          border-radius: 12px;
          padding: 10px;
          background: #f7faff;
          color: #31578f;
          cursor: pointer;
          font: inherit;
          font-size: 12px;
          font-weight: 700;
        }
        .mc-auth__form {
          display: grid;
          gap: 16px;
        }
        .mc-auth__field {
          display: grid;
          gap: 7px;
        }
        .mc-auth__field label {
          color: #344d70;
          font-size: 12px;
          font-weight: 800;
        }
        .mc-auth__input {
          display: flex;
          align-items: center;
          gap: 10px;
          min-height: 48px;
          padding: 0 13px;
          border: 1px solid #c7d7ef;
          border-radius: 12px;
          background: #fff;
        }
        .mc-auth__input:focus-within {
          border-color: #6e94d9;
          box-shadow: 0 0 0 3px #7399df22;
        }
        .mc-auth__input .material-symbols-outlined {
          color: #5979af;
        }
        .mc-auth__input input,
        .mc-auth__input select {
          width: 100%;
          border: 0;
          outline: 0;
          background: transparent;
          color: #1a3357;
          font: inherit;
          font-size: 14px;
        }
        .mc-auth__icon {
          border: 0;
          background: transparent;
          color: #5574a9;
          cursor: pointer;
        }
        .mc-auth__label-row {
          display: flex;
          justify-content: space-between;
        }
        .mc-auth__label-row a {
          color: #4167b2;
          font-size: 11px;
          text-decoration: none;
        }
        .mc-auth__error {
          margin: 0;
          color: #b74151;
          font-size: 12px;
          font-weight: 700;
        }
        .mc-auth__submit {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          min-height: 50px;
          border: 0;
          border-radius: 999px;
          background: linear-gradient(100deg, #7d9ce4, #4167b2);
          color: #fff;
          cursor: pointer;
          font: inherit;
          font-size: 14px;
          font-weight: 800;
          box-shadow: 0 10px 22px #4167b238;
        }
        .mc-auth__submit:disabled,
        .mc-auth__demo button:disabled {
          opacity: 0.65;
          cursor: not-allowed;
        }
        .mc-auth__switch {
          margin: 20px 0 0;
          color: #657790;
          text-align: center;
          font-size: 13px;
        }
        .mc-auth__switch button {
          border: 0;
          background: transparent;
          color: #4167b2;
          cursor: pointer;
          font: inherit;
          font-weight: 800;
        }
        .mc-auth__guest {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          margin-top: 20px;
          color: #4167b2;
          text-decoration: none;
          font-size: 13px;
          font-weight: 700;
        }
        @media (max-width: 850px) {
          .mc-auth__layout {
            grid-template-columns: 1fr;
            gap: 30px;
          }
          .mc-auth__intro h1 {
            font-size: 52px;
          }
          .mc-auth__points {
            display: none;
          }
          .mc-auth__card {
            max-width: 520px;
            width: 100%;
            margin: auto;
          }
        }
        @media (max-width: 560px) {
          .mc-auth__shell {
            width: min(100% - 24px, 1180px);
          }
          .mc-auth__header {
            height: 74px;
          }
          .mc-auth__logo {
            width: 120px;
            height: 38px;
          }
          .mc-auth__back span {
            display: none;
          }
          .mc-auth__layout {
            min-height: 0;
            padding: 30px 18px 38px;
            border-radius: 20px;
          }
          .mc-auth__intro h1 {
            font-size: 43px;
          }
          .mc-auth__intro p:not(.mc-auth__eyebrow) {
            font-size: 14px;
          }
          .mc-auth__card {
            padding: 23px 18px;
          }
          .mc-auth__demo {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
      <div className="mc-auth__shell">
        <header className="mc-auth__header">
          <Link href="/" className="mc-auth__logo" aria-label="MediCheck">
            <Image
              src={asset("2-cropped.png")}
              alt="MediCheck"
              fill
              sizes="190px"
              priority
            />
          </Link>
          <Link href="/" className="mc-auth__back">
            <MaterialIcon name="arrow_back" size={18} />
            <span>Về trang chủ</span>
          </Link>
        </header>
        <section className="mc-auth__layout">
          <MediFox variant="loading" className="mc-auth__mascot" />
          <div className="mc-auth__intro">
            <p className="mc-auth__eyebrow">
              <b>✓</b> MEDICHECK ACCOUNT
            </p>
            <h1>
              {mode === "login" ? (
                <>
                  Chào mừng
                  <br />
                  <em>trở lại.</em>
                </>
              ) : (
                <>
                  Bắt đầu hành trình
                  <br />
                  <em>an toàn hơn.</em>
                </>
              )}
            </h1>
            <p>
              {mode === "login"
                ? "Đăng nhập để tiếp tục theo dõi và kiểm tra tương tác thuốc trong hành trình điều trị của bạn."
                : "Tạo tài khoản MediCheck để quản lý thông tin thuốc và chủ động bảo vệ sức khỏe mỗi ngày."}
            </p>
            <div className="mc-auth__points">
              <span className="mc-auth__point">
                <MaterialIcon name="verified_user" size={20} />
                Dữ liệu y tế đáng tin cậy
              </span>
              <span className="mc-auth__point">
                <MaterialIcon name="history" size={20} />
                Lưu lại lịch sử tra cứu
              </span>
              <span className="mc-auth__point">
                <MaterialIcon name="health_and_safety" size={20} />
                Đồng hành cùng sức khỏe của bạn
              </span>
            </div>
          </div>
          <section className="mc-auth__card">
            <div className="mc-auth__tabs">
              <button
                type="button"
                className={
                  mode === "login"
                    ? "mc-auth__tab mc-auth__tab--active"
                    : "mc-auth__tab"
                }
                onClick={() => changeMode("login")}
              >
                Đăng nhập
              </button>
              <button
                type="button"
                className={
                  mode === "register"
                    ? "mc-auth__tab mc-auth__tab--active"
                    : "mc-auth__tab"
                }
                onClick={() => changeMode("register")}
              >
                Đăng ký
              </button>
            </div>
            <h2 className="mc-auth__title">
              {mode === "login" ? "Đăng nhập MediCheck" : "Tạo tài khoản mới"}
            </h2>
            <p className="mc-auth__subtitle">
              {mode === "login"
                ? "Nhập thông tin của bạn để tiếp tục."
                : "Điền thông tin bên dưới để bắt đầu trải nghiệm."}
            </p>
            {mode === "login" && (
              <div className="mc-auth__demo">
                <button
                  type="button"
                  onClick={() => demo("demo-pharmacist@medguard.local")}
                  disabled={loading}
                >
                  Dược sĩ Demo
                </button>
                <button
                  type="button"
                  onClick={() => demo("demo-patient@medguard.local")}
                  disabled={loading}
                >
                  Người dùng Demo
                </button>
              </div>
            )}
            <form className="mc-auth__form" onSubmit={submit}>
              {mode === "register" && (
                <>
                  <div className="mc-auth__field">
                    <label htmlFor="ho_ten">Họ tên</label>
                    <div className="mc-auth__input">
                      <MaterialIcon name="person" size={20} />
                      <input
                        id="ho_ten"
                        required
                        value={hoTen}
                        onChange={(event) => setHoTen(event.target.value)}
                        placeholder="Nguyễn Văn A"
                      />
                    </div>
                  </div>
                  <div className="mc-auth__field">
                    <label htmlFor="role">Vai trò</label>
                    <div className="mc-auth__input">
                      <MaterialIcon name="badge" size={20} />
                      <select
                        id="role"
                        value={role}
                        onChange={(event) =>
                          setRole(event.target.value as Role)
                        }
                      >
                        <option value="patient">Người dùng</option>
                        <option value="pharmacist">Dược sĩ</option>
                      </select>
                    </div>
                  </div>
                </>
              )}
              <div className="mc-auth__field">
                <label htmlFor="email">Email</label>
                <div className="mc-auth__input">
                  <MaterialIcon name="mail" size={20} />
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="ban@vidu.com"
                  />
                </div>
              </div>
              <div className="mc-auth__field">
                <div className="mc-auth__label-row">
                  <label htmlFor="mat_khau">Mật khẩu</label>
                  {mode === "login" && (
                    <a href="#" onClick={(event) => event.preventDefault()}>
                      Quên mật khẩu?
                    </a>
                  )}
                </div>
                <div className="mc-auth__input">
                  <MaterialIcon name="lock" size={20} />
                  <input
                    id="mat_khau"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={6}
                    value={matKhau}
                    onChange={(event) => setMatKhau(event.target.value)}
                    placeholder="Tối thiểu 6 ký tự"
                  />
                  <button
                    type="button"
                    className="mc-auth__icon"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  >
                    <MaterialIcon
                      name={showPassword ? "visibility_off" : "visibility"}
                      size={20}
                    />
                  </button>
                </div>
              </div>
              {error && (
                <p className="mc-auth__error" role="alert">
                  {error}
                </p>
              )}
              <button
                type="submit"
                className="mc-auth__submit"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="spinner" />
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
            <p className="mc-auth__switch">
              {mode === "login" ? (
                <>
                  Chưa có tài khoản?{" "}
                  <button type="button" onClick={() => changeMode("register")}>
                    Đăng ký ngay
                  </button>
                </>
              ) : (
                <>
                  Đã có tài khoản?{" "}
                  <button type="button" onClick={() => changeMode("login")}>
                    Đăng nhập
                  </button>
                </>
              )}
            </p>
          </section>
        </section>
      </div>
    </main>
  );
}
