"use client";

import { useEffect, useState, type FormEvent } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import AlertCard from "@/components/AlertCard";
import PrescriptionPanel from "@/components/PrescriptionPanel";
import { ApiError, checkGuestProducts, checkProducts, listPatientMedications, searchGuestProducts, searchProducts, type MedicationCheckResponse, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { createPrescription, drugOrigins, isCrossPrescription, mergedDrugNames, originLabel, type Prescription } from "@/lib/prescription";

const POSITIONS = [[50, 16], [84, 38], [68, 82], [32, 82], [16, 38]];
const severityColor: Record<string, string> = { nang: "#c94740", trung_binh: "#c58a32", nhe: "#5d9b78", chua_phan_loai: "#8d98a4" };

function InteractionSource({ source }: { source: string }) {
  const [open, setOpen] = useState(false);
  return <span className={`citation-wrap ${open ? "citation-wrap--open" : ""}`}><button type="button" className="citation-trigger" aria-expanded={open} onClick={() => setOpen((value) => !value)}><MaterialIcon name="database" size={15} /><span className="citation-trigger__text">{source || "Nguồn trích dẫn"}</span><MaterialIcon name={open ? "expand_less" : "expand_more"} size={16} /></button><span className="citation-popover" role="tooltip"><span className="citation-popover__label">NGUỒN THAM KHẢO</span><strong>{source || "Chưa có thông tin nguồn"}</strong><p>Nguồn dữ liệu được dùng để giải thích cảnh báo tương tác này.</p></span></span>;
}

export default function InteractionPage() {
  const session = getSession();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(() => [createPrescription(1)]);
  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllPairs, setShowAllPairs] = useState(false);

  const boardMode = prescriptions.length > 1;
  const primary = prescriptions[0];

  useEffect(() => {
    if (query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => (session ? searchProducts(query.trim(), session.accessToken) : searchGuestProducts(query.trim())).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  useEffect(() => {
    if (!session) return;
    listPatientMedications(session.userId, session.accessToken)
      .then((items) => setPrescriptions((prev) => prev.map((p, index) => (index === 0 ? { ...p, drugs: items.map((item) => ({ name: item.ten_thuoc, known: true })) } : p))))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const searchFn = (q: string) => (session ? searchProducts(q, session.accessToken) : searchGuestProducts(q));

  function addDrugTo(prescriptionId: string, name: string, known = true) {
    setPrescriptions((prev) => prev.map((p) => {
      if (p.id !== prescriptionId) return p;
      if (p.drugs.some((d) => d.name.toLowerCase() === name.toLowerCase())) return p;
      return { ...p, drugs: [...p.drugs, { name, known }] };
    }));
    setResult(null);
  }

  function removeDrugFrom(prescriptionId: string, name: string) {
    setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, drugs: p.drugs.filter((d) => d.name !== name) } : p)));
    setResult(null);
  }

  function addDrug(name: string, known = true) {
    addDrugTo(primary.id, name, known);
    setQuery(""); setSuggestions([]);
  }

  function addPrescription() {
    setPrescriptions((prev) => [...prev, createPrescription(prev.length + 1)]);
    setQuery(""); setSuggestions([]);
  }

  function removePrescription(id: string) {
    setPrescriptions((prev) => (prev.length <= 1 ? prev : prev.filter((p) => p.id !== id)));
    setResult(null);
  }

  async function importFromProfile(prescriptionId: string) {
    if (!session) return;
    try {
      const items = await listPatientMedications(session.userId, session.accessToken);
      setPrescriptions((prev) => prev.map((p) => {
        if (p.id !== prescriptionId) return p;
        const existing = new Set(p.drugs.map((d) => d.name.toLowerCase()));
        const toAdd = items.filter((item) => !existing.has(item.ten_thuoc.toLowerCase())).map((item) => ({ name: item.ten_thuoc, known: true }));
        return toAdd.length ? { ...p, drugs: [...p.drugs, ...toAdd] } : p;
      }));
      setResult(null);
    } catch { /* import lỗi âm thầm bỏ qua, người dùng vẫn có thể nhập tay */ }
  }

  async function runCheck(e?: FormEvent) {
    e?.preventDefault();
    const names = mergedDrugNames(prescriptions);
    if (names.length < 2) { setError("Hãy chọn ít nhất 2 thuốc để phân tích tương tác."); return; }
    setError(null); setLoading(true);
    try { const data = session ? await checkProducts(names, session.accessToken) : await checkGuestProducts(names); setResult(data); window.sessionStorage.setItem("medguard_last_check", JSON.stringify(data)); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không thể phân tích tương tác lúc này."); }
    finally { setLoading(false); }
  }

  const flatSelected = prescriptions.flatMap((p) => p.drugs);
  const origins = drugOrigins(prescriptions);
  const explanationsAll = result?.explanations ?? [];
  const explanations = boardMode && !showAllPairs ? explanationsAll.filter((item) => isCrossPrescription(origins, item.thuoc_a, item.thuoc_b)) : explanationsAll;
  const crossCount = explanationsAll.filter((item) => isCrossPrescription(origins, item.thuoc_a, item.thuoc_b)).length;

  const needsUpdate = Boolean(result?.has_unclassified || flatSelected.some((item) => !item.known) || result?.explanations?.some((item) => !item.muc_do || item.muc_do === "chua_phan_loai"));
  const severe = explanations.find((item) => item.muc_do === "nang") ?? explanations[0];
  function focusPair(index: number) {
    if (index < 0) return;
    const card = document.getElementById(`interaction-pair-${index}`);
    card?.scrollIntoView({ behavior: "smooth", block: "center" });
    card?.classList.add("interaction-pair--focused");
    window.setTimeout(() => card?.classList.remove("interaction-pair--focused"), 1800);
  }
  const links = flatSelected.slice(0, 5).flatMap((drug, index) => flatSelected.slice(index + 1, 5).map((target, targetIndex) => {
    const pair = explanations.find((item) => {
      const names = [item.thuoc_a?.toLowerCase(), item.thuoc_b?.toLowerCase()];
      return names.includes(drug.name.toLowerCase()) && names.includes(target.name.toLowerCase());
    });
    const pairIndex = pair ? explanationsAll.indexOf(pair) : -1;
    return { from: index, to: index + 1 + targetIndex, severity: pair?.muc_do, pairIndex };
  }));

  return <main className="interaction-page">{!session && <div className="guest-mode-banner"><MaterialIcon name="visibility" size={18} /><span>Chế độ khách: kết quả chỉ hiển thị tạm thời và không được lưu vào lịch sử.</span></div>}
    <section className="page-intro"><p className="eyebrow">PHÂN TÍCH AN TOÀN</p><h1>Kiểm Tra Tương Tác Thuốc</h1><p>Thêm thuốc mới vào đơn hiện tại để xem phân tích tương tác tức thì, hoặc thêm nhiều đơn thuốc để so sánh cùng lúc.</p></section>

    {!boardMode && <form className="interaction-search panel" onSubmit={(e) => { e.preventDefault(); if (query.trim() && suggestions.length === 0) addDrug(query.trim(), false); else void runCheck(e); }}><label htmlFor="interaction-search">Tìm kiếm thuốc</label><div className="interaction-search__input"><MaterialIcon name="search" size={21} /><input id="interaction-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập tên thuốc, ví dụ Panadol" autoComplete="off" />{query && <button type="button" onClick={() => { setQuery(""); setSuggestions([]); }} aria-label="Xóa tìm kiếm"><MaterialIcon name="close" size={18} /></button>}</div>{suggestions.length > 0 ? <ul className="interaction-suggestions">{suggestions.slice(0, 5).map((item) => <li key={item.id} onClick={() => addDrug(item.ten_thuoc)}><div><strong>{item.ten_thuoc}</strong><small>Thuốc trong cơ sở dữ liệu</small></div><MaterialIcon name="add_circle_outline" size={21} /></li>)}</ul> : query.trim().length >= 2 && <button type="button" className="interaction-unknown" onClick={() => addDrug(query.trim(), false)}><div><strong>Không tìm thấy "{query.trim()}"</strong><small>Thêm thuốc chưa cập nhật trong cơ sở dữ liệu</small></div><MaterialIcon name="add_circle_outline" size={21} /></button>}</form>}

    {error && <p className="error-text" role="alert">{error}</p>}
    {result && ((result.unknown_products?.length ?? 0) > 0 || (result.no_interaction_data_products?.length ?? 0) > 0) && <div className="guest-mode-banner"><MaterialIcon name="info" size={18} /><span>{result.unknown_products && result.unknown_products.length > 0 && `Không tìm thấy trong CSDL: ${result.unknown_products.join(", ")}. `}{result.no_interaction_data_products && result.no_interaction_data_products.length > 0 && `Chưa có dữ liệu hoạt chất để kiểm tra tương tác: ${result.no_interaction_data_products.join(", ")}.`}</span></div>}

    {boardMode && <section className="prescription-board-wrap">
      <div className="prescription-board">
        {prescriptions.map((p) => (
          <PrescriptionPanel key={p.id} label={p.label} drugs={p.drugs} search={searchFn}
            onAdd={(name, known) => addDrugTo(p.id, name, known)}
            onRemoveDrug={(name) => removeDrugFrom(p.id, name)}
            onRemovePanel={() => removePrescription(p.id)}
            onImport={session ? () => importFromProfile(p.id) : undefined}
            inputId={`prescription-search-${p.id}`} />
        ))}
        <button type="button" className="prescription-board__add" onClick={addPrescription}>
          <MaterialIcon name="add_circle" size={26} /><span>Thêm đơn thuốc</span>
        </button>
      </div>
      <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || mergedDrugNames(prescriptions).length < 2}>
        <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
      </button>
    </section>}

    <div className={boardMode ? "interaction-workspace interaction-workspace--board" : "interaction-workspace"}>
      {!boardMode && <aside className="interaction-selection panel"><div className="interaction-selection__header"><h2>Thuốc đang chọn</h2><span>{primary.drugs.length}</span></div>{primary.drugs.length === 0 && <div className="interaction-selection__empty"><MaterialIcon name="medication" size={34} /><p>Chọn thuốc ở ô tìm kiếm phía trên để bắt đầu.</p></div>}{primary.drugs.map((item, index) => <div className={`selected-medication ${!item.known ? "selected-medication--unknown" : ""}`} key={item.name}><span className="selected-medication__icon"><MaterialIcon name="medication" size={21} /></span><div><strong>{item.name}</strong><small>{item.known ? (index === 0 ? "Thuốc hiện tại" : "Thuốc mới thêm") : "Chưa cập nhật trong cơ sở dữ liệu"}</small></div><button type="button" onClick={() => removeDrugFrom(primary.id, item.name)} aria-label={`Xóa ${item.name}`}><MaterialIcon name="close" size={19} /></button></div>)}<button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || primary.drugs.length < 2}><MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}</button><button type="button" className="prescription-add-link" onClick={addPrescription}><MaterialIcon name="add_circle_outline" size={17} /> Thêm đơn thuốc để so sánh nhiều đơn</button></aside>}

      <section className="interaction-result panel"><div className="interaction-result__header"><div><p className="eyebrow">ĐỒ THỊ TƯƠNG TÁC</p><h2>{result ? "Kết quả phân tích" : "Mối liên hệ giữa các thuốc"}</h2></div>{result && <span className={result.has_severe ? "result-pill result-pill--danger" : needsUpdate ? "result-pill result-pill--unknown" : "result-pill"}>{result.has_severe ? "Cần lưu ý" : needsUpdate ? "Chưa cập nhật" : "An toàn"}</span>}</div>
        <div className="ddinter-graph">{flatSelected.length > 0 ? <svg viewBox="0 0 100 100" role="img" aria-label="Đồ thị tương tác thuốc">{links.map((link) => <line className="ddinter-edge" key={`${link.from}-${link.to}`} onClick={() => focusPair(link.pairIndex)} x1={POSITIONS[link.from][0]} y1={POSITIONS[link.from][1]} x2={POSITIONS[link.to][0]} y2={POSITIONS[link.to][1]} stroke={severityColor[link.severity ?? ""] ?? "#9bb1c9"} strokeWidth={link.severity ? 1.5 : 1} strokeDasharray={link.severity === "chua_phan_loai" ? "2 2" : undefined} />)}{flatSelected.slice(0, 5).map((item, index) => <g className={`ddinter-node ${!item.known ? "ddinter-node--unknown" : ""}`} key={item.name} transform={`translate(${POSITIONS[index][0]} ${POSITIONS[index][1]})`}><circle r="8" /><text y="1" textAnchor="middle">{index + 1}</text><text className="ddinter-node__label" y="13" textAnchor="middle">{item.name.length > 17 ? `${item.name.slice(0, 17)}…` : item.name}</text></g>)}</svg> : <div className="graph-placeholder"><MaterialIcon name="hub" size={42} /><span>Đồ thị sẽ hiển thị sau khi bạn chọn thuốc</span></div>}</div>
        <div className="ddinter-legend"><span><i className="legend-dot legend-dot--severe" /> Nghiêm trọng</span><span><i className="legend-dot legend-dot--moderate" /> Trung bình</span><span><i className="legend-dot legend-dot--unknown" /> Chưa cập nhật</span></div>
        {severe ? <article className={`interaction-alert ${!severe.muc_do || severe.muc_do === "chua_phan_loai" ? "interaction-alert--unknown" : severe.muc_do === "trung_binh" ? "interaction-alert--moderate" : severe.muc_do === "nhe" ? "interaction-alert--mild" : ""}`}><MaterialIcon name={!severe.muc_do || severe.muc_do === "chua_phan_loai" ? "help" : severe.muc_do === "trung_binh" ? "warning" : "dangerous"} size={22} filled /><div><strong>{!severe.muc_do || severe.muc_do === "chua_phan_loai" ? "CHƯA CẬP NHẬT" : `TƯƠNG TÁC ${severe.muc_do === "nang" ? "NGHIÊM TRỌNG" : "CẦN LƯU Ý"}`}</strong><p>{!severe.muc_do || severe.muc_do === "chua_phan_loai" ? "Chưa có đủ dữ liệu để kết luận mức độ an toàn của tương tác này." : severe.giai_thich}</p><InteractionSource source={severe.nguon_trich_dan} /></div></article> : <div className="interaction-alert interaction-alert--empty"><MaterialIcon name="info" size={20} /><span>{flatSelected.length < 2 ? "Chọn ít nhất 2 thuốc để xem cảnh báo tương tác." : "Nhấn phân tích để kiểm tra tương tác."}</span></div>}
      </section>
    </div>

    {result && explanationsAll.length > 0 && <section className="interaction-pairs">
      <div className="dashboard-section__header"><h2><MaterialIcon name="fact_check" size={21} /> Phân tích theo từng cặp thuốc</h2><span>{explanations.length} cặp tương tác</span></div>
      {boardMode && <button type="button" className="interaction-pairs__toggle" onClick={() => setShowAllPairs((v) => !v)}>
        <MaterialIcon name={showAllPairs ? "visibility_off" : "visibility"} size={17} />
        {showAllPairs ? "Chỉ xem tương tác giữa các đơn" : `Xem tất cả tương tác (bao gồm trong cùng đơn) — còn ${explanationsAll.length - crossCount} cặp`}
      </button>}
      {explanations.map((item, index) => { const globalIndex = explanationsAll.indexOf(item); const origin = boardMode ? originLabel(prescriptions, origins, item.thuoc_a, item.thuoc_b) : null; return <div id={`interaction-pair-${globalIndex}`} className="interaction-pair-card" key={`${item.thuoc_a}-${item.thuoc_b}-${index}`}>{origin && <span className="interaction-pair-card__origin">{origin}</span>}<AlertCard thuocA={item.thuoc_a} thuocB={item.thuoc_b} severity={item.muc_do} description={item.giai_thich} source={item.nguon_trich_dan} /></div>; })}
    </section>}
  </main>;
}
