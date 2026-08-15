import "./globals.css";
import FrontendBootGate from "@/components/FrontendBootGate";

export const metadata = {
  title: "MediCheck",
  description: "Nền tảng kiểm tra tương tác thuốc thông minh",
  icons: {
    icon: "/Bộ nhận diện y tế/1-cropped.png",
  },
};

export const viewport = {
  themeColor: "#005eb8",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0..1,0"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
        <FrontendBootGate />
      </body>
    </html>
  );
}
