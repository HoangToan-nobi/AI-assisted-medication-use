"use client";

import { useEffect, useState } from "react";

export default function FrontendBootGate() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const dismiss = () => requestAnimationFrame(() => setVisible(false));
    if (document.readyState === "complete") {
      dismiss();
      return;
    }

    window.addEventListener("load", dismiss, { once: true });
    const fallback = window.setTimeout(dismiss, 2500);
    return () => {
      window.removeEventListener("load", dismiss);
      window.clearTimeout(fallback);
    };
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="MediCheck đang tải"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background: "#f7faff",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          maxWidth: 440,
          padding: "22px 26px",
          border: "1px solid #d5e1f7",
          borderRadius: 22,
          background: "#ffffff",
          boxShadow: "0 18px 42px rgba(49, 78, 130, 0.14)",
          color: "#1d315c",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <img
          src={encodeURI("/Bộ nhận diện y tế/12-cropped.png")}
          alt=""
          width={82}
          height={70}
          style={{ objectFit: "contain" }}
        />
        <div>
          <strong style={{ display: "block", fontSize: 17 }}>Cáo Medi đang chuẩn bị trang cho bạn...</strong>
          <span style={{ display: "block", marginTop: 6, color: "#687b9b", fontSize: 14 }}>Vui lòng chờ trong giây lát.</span>
        </div>
      </div>
    </div>
  );
}
