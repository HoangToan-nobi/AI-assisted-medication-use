"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  addPatientMedication,
  searchMedications,
  type MedicationSearchResult,
} from "@/lib/api";
import { getSession } from "@/lib/auth";

export default function MedicationsPage() {
  const router = useRouter();
  const session = getSession();

  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<MedicationSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!session || query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      searchMedications(query.trim(), session.accessToken)
        .then(setSuggestions)
        .catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function handleSave(name: string) {
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      await addPatientMedication(session.userId, name, session.accessToken);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không thêm được thuốc");
    } finally {
      setSaving(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (query.trim()) handleSave(query.trim());
  }

  if (!session) return null;

  return (
    <main>
      <h1>Thêm thuốc</h1>
      <div className="panel">
        <form onSubmit={handleSubmit}>
          <div className="field autocomplete">
            <label htmlFor="medication_name">Tên thuốc (kể cả viết tắt/biệt dược)</label>
            <input
              id="medication_name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="VD: aspirin, panadol, warfarin..."
              autoComplete="off"
            />
            {suggestions.length > 0 && (
              <ul className="autocomplete-list">
                {suggestions.map((s) => (
                  <li
                    key={s.id}
                    onClick={() => {
                      setQuery(s.ten_chuan_hoa);
                      setSuggestions([]);
                    }}
                  >
                    {s.ten_chuan_hoa}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" disabled={saving || !query.trim()} style={{ width: "100%" }}>
            {saving && <span className="spinner" aria-hidden="true" />}
            {saving ? "Đang lưu..." : "Lưu vào hồ sơ"}
          </button>
        </form>
      </div>
    </main>
  );
}
