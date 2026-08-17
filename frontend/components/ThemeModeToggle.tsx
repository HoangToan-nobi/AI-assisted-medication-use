"use client";

import { useEffect, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";

type Theme = "light" | "dark";
const STORAGE_KEY = "medicheck_theme";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem(STORAGE_KEY, theme);
}

export default function ThemeModeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
    const preferred: Theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const next = saved === "dark" || saved === "light" ? saved : preferred;
    setTheme(next);
    applyTheme(next);
  }, []);

  function toggleTheme() {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
  }

  return (
    <button
      type="button"
      className={`theme-toggle theme-toggle--${theme}`}
      onClick={toggleTheme}
      aria-label={theme === "light" ? "Chuyển sang giao diện tối" : "Chuyển sang giao diện sáng"}
      title={theme === "light" ? "Giao diện tối" : "Giao diện sáng"}
    >
      <MaterialIcon name="light_mode" size={17} />
      <MaterialIcon name="dark_mode" size={17} />
      <span className="theme-toggle__clouds" aria-hidden="true"><i /><i /><i /></span>
      <span className="theme-toggle__stars" aria-hidden="true"><i /><i /><i /></span>
      <span className="theme-toggle__thumb" aria-hidden="true" />
    </button>
  );
}
