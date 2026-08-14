import Link from 'next/link';
import Image from 'next/image';

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
      </footer>
    </div>
  );
}
