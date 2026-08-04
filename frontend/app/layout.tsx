import "./globals.css";

export const metadata = {
  title: "MedGuard AI",
  description: "Trợ lý AI kiểm tra tương tác thuốc an toàn",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
