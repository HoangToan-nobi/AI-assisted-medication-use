"use client";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import BrandLogo from "@/components/BrandLogo";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, login } from "@/lib/api";
import { saveSession } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const handleDemoLogin = async (demoEmail: string) => {
    setError(null);
    setLoading(true);
    setEmail(demoEmail);
    setPassword("demo1234");
    try {
      const auth = await login(demoEmail, "demo1234");
      saveSession({
        accessToken: auth.access_token,
        userId: auth.user_id,
        hoTen: auth.ho_ten,
        vaiTro: auth.vai_tro,
      });
      router.push(auth.vai_tro === "patient" ? "/dashboard" : "/pharmacist-dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Có lỗi xảy ra. Hãy đảm bảo bạn đã chạy scripts/seed_demo_users.py");
    } finally {
      setLoading(false);
    }
  };

  async function submit(event: FormEvent) { event.preventDefault(); setLoading(true); setError(null); try { const auth = await login(email, password); saveSession({ accessToken: auth.access_token, userId: auth.user_id, hoTen: auth.ho_ten, vaiTro: auth.vai_tro }); router.push(auth.vai_tro === "patient" ? "/dashboard" : "/pharmacist-dashboard"); } catch (err) { setError(err instanceof ApiError ? err.message : "Không thể đăng nhập."); } finally { setLoading(false); } }
  return <div className="auth-shell"><BrandLogo size="lg" showTagline /><div className="auth-card"><h2 className="auth-card__heading">Đăng nhập tài khoản</h2>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
            <button
              type="button"
              className="btn-block"
              style={{ backgroundColor: '#e2e8f0', color: '#0f172a', fontSize: '14px', padding: '8px' }}
              onClick={() => handleDemoLogin("demo-pharmacist@medguard.local")}
              disabled={loading}
            >
              👩‍⚕️ Dược sĩ Demo
            </button>
            <button
              type="button"
              className="btn-block"
              style={{ backgroundColor: '#e2e8f0', color: '#0f172a', fontSize: '14px', padding: '8px' }}
              onClick={() => handleDemoLogin("demo-patient@medguard.local")}
              disabled={loading}
            >
              👤 Người dùng Demo
            </button>
          </div>
<form onSubmit={submit}><div className="field"><label>Email</label><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ban@vidu.com" /></div><div className="field"><label>Mật khẩu</label><input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>{error && <p className="error-text">{error}</p>}<button className="btn-block" disabled={loading}>{loading ? <span className="spinner" /> : <>Đăng nhập <MaterialIcon name="arrow_forward" size={20} /></>}</button></form><p className="auth-footer"><Link href="/interaction">Tiếp tục tra cứu với tư cách khách</Link></p></div></div>;
}
