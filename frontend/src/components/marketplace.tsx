"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Circle,
  LayoutGrid,
  List,
  MapPin,
  Package,
  Plus,
  RefreshCw,
  Route,
  Search,
  SlidersHorizontal,
  Truck,
  X,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Load } from "@/lib/types";
import { LoadCard } from "./load-card";
import { Empty, ErrorBox, Loading } from "./ui";
import { useSaved } from "./use-saved";
import { useSession } from "./session";

const defaultFilters = {
  origin: "",
  destination: "",
  vehicle: "",
  weight: "",
  search: "",
};
export function Marketplace({ onlySaved = false }: { onlySaved?: boolean }) {
  const { t } = useLocale();

  const { user } = useSession();
  const [loads, setLoads] = useState<Load[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(defaultFilters);
  const [filters, setFilters] = useState(defaultFilters);
  const [sort, setSort] = useState("newest");
  const [layout, setLayout] = useState("grid");
  const [page, setPage] = useState(1);
  const [advanced, setAdvanced] = useState(false);
  const { saved, toggle } = useSaved();
  async function refresh(quiet = false) {
    setError("");
    if (!quiet) setLoading(true);
    try {
      setLoads(
        await api<Load[]>(`cargo/loads/${onlySaved ? "" : "?status=open"}`),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh(true);
    }, 60000);
    return () => clearInterval(timer);
  }, [user?.id, onlySaved]);
  const visible = useMemo(() => {
    const match = (value: string, query: string) =>
      value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
    const result = loads.filter(
      (load) =>
        (!onlySaved || saved.includes(load.id)) &&
        match(load.origin, filters.origin) &&
        match(load.destination, filters.destination) &&
        (!filters.vehicle ||
          ({
            tent: /tent|тент|тэнт/i,
            ref: /ref|реф/i,
            fura: /fura|фур/i,
            bort: /bort|борт/i,
          }[filters.vehicle]?.test(load.vehicle_type) ??
            match(load.vehicle_type, filters.vehicle))) &&
        (!filters.weight ||
          Number(load.weight_tons) <= Number(filters.weight)) &&
        match(
          `${load.cargo_name} ${load.origin} ${load.destination}`,
          filters.search,
        ),
    );
    return result.sort((a, b) =>
      sort === "weight"
        ? Number(b.weight_tons) - Number(a.weight_tons)
        : sort === "oldest"
          ? a.id - b.id
          : b.id - a.id,
    );
  }, [loads, filters, sort, onlySaved, saved]);
  const pages = Math.max(1, Math.ceil(visible.length / 9));
  const currentPage = Math.min(page, pages);
  const activeFilters = Object.values(filters).some(Boolean);
  function change(name: keyof typeof draft, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }
  function reset() {
    setDraft(defaultFilters);
    setFilters(defaultFilters);
    setPage(1);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span />
            {onlySaved ? t("SIZ TANLAGAN YO‘NALISHLAR") : t("YUKLAR BIRJASI")}
          </div>
          <h1>
            {onlySaved
              ? t("Saqlangan yuklar")
              : t("Yuk toping. Yo‘lga chiqing.")}
          </h1>
          <p>
            {onlySaved
              ? t("Kerakli e’lonlar bir joyda. Ushbu brauzerda saqlanadi.")
              : t("Sizga mos yo‘nalish, kerakli yuk — barchasi bir joyda.")}
          </p>
        </div>
        <Link href="/loads/new" className="button primary">
          <Plus size={18} />
          {t("Yuk joylash")}
        </Link>
      </div>
      {!onlySaved && (
        <section className="market-hero">
          <div className="hero-copy">
            <span className="hero-kicker">
              <span />
              {t("HAR BIR YO‘L — YANGI IMKONIYAT")}
            </span>
            <h2>
              {t("Bo‘sh qaytmang.")}
              <br />
              <em>{t("Keyingi yukingizni toping.")}</em>
            </h2>
            <p>
              {t("Yaqin va uzoq yo‘nalishlar uchun aktual e’lonlar.")}
              <br />
              {t("Yuk beruvchi bilan bevosita bog‘laning.")}
            </p>
            <a href="#load-search">
              {t("Yo‘nalish tanlash")}
              <ArrowUpRight size={17} />
            </a>
          </div>
          <div className="route-art" aria-hidden="true">
            <div className="route-art-grid" />
            <svg viewBox="0 0 410 235" fill="none">
              <path
                d="M20 185H94Q125 185 125 154V100Q125 68 157 68H260Q292 68 292 37V18"
                stroke="#3e6855"
                strokeWidth="28"
              />
              <path
                d="M20 185H94Q125 185 125 154V100Q125 68 157 68H260Q292 68 292 37V18"
                stroke="#c9ee8b"
                strokeWidth="2"
                strokeDasharray="6 8"
              />
              <circle cx="63" cy="185" r="11" fill="#c9ee8b" />
              <circle cx="63" cy="185" r="4" fill="#173e35" />
              <circle cx="292" cy="31" r="11" fill="#c9ee8b" />
              <circle cx="292" cy="31" r="4" fill="#173e35" />
            </svg>
            <span className="art-city city-a">{t("TOSHKENT")}</span>
            <span className="art-city city-b">{t("SAMARQAND")}</span>
            <span className="truck-badge">
              <Truck size={38} strokeWidth={1.5} />
            </span>
            <div className="art-label">
              <span>
                <Check size={13} />
              </span>
              {t("Yo‘lingizga mos yuk")}
            </div>
          </div>
        </section>
      )}
      {!onlySaved && (
        <div className="market-stats">
          <div>
            <span className="stat-icon">
              <Package size={20} />
            </span>
            <strong>{loading ? "—" : loads.length}</strong>
            <span>{t("aktual yuk")}</span>
          </div>
          <div>
            <span className="stat-icon">
              <Route size={20} />
            </span>
            <strong>
              {loading
                ? "—"
                : new Set(loads.map((l) => `${l.origin}-${l.destination}`))
                    .size}
            </strong>
            <span>{t("yo‘nalish")}</span>
          </div>
          <Link href="/saved">
            <span className="stat-icon">
              <Bookmark size={20} />
            </span>
            <strong>{saved.length}</strong>
            <span>{t("saqlangan e’lon")}</span>
            <ArrowUpRight size={16} />
          </Link>
        </div>
      )}
      <section className="search-panel" id="load-search">
        <div className="section-kicker">
          <SlidersHorizontal size={17} />
          <strong>{t("Yo‘nalish bo‘yicha qidirish")}</strong>
          <button
            className="text-button"
            onClick={() => setAdvanced(!advanced)}
          >
            {advanced ? t("Kamroq filtr") : t("Barcha filtrlar")}
            <Plus size={14} />
          </button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFilters(draft);
            setPage(1);
          }}
        >
          <div className="search-fields">
            <label className="search-field">
              <span>{t("Qayerdan")}</span>
              <div>
                <Circle size={16} />
                <input
                  aria-label={t("Qayerdan")}
                  placeholder={t("Shahar yoki viloyat")}
                  value={draft.origin}
                  onChange={(e) => change("origin", e.target.value)}
                />
              </div>
            </label>
            <button
              type="button"
              className="swap-button"
              aria-label={t("Yo‘nalishni almashtirish")}
              onClick={() =>
                setDraft({
                  ...draft,
                  origin: draft.destination,
                  destination: draft.origin,
                })
              }
            >
              <ArrowDownUp size={17} />
            </button>
            <label className="search-field">
              <span>{t("Qayerga")}</span>
              <div>
                <MapPin size={17} />
                <input
                  aria-label={t("Qayerga")}
                  placeholder={t("Shahar yoki viloyat")}
                  value={draft.destination}
                  onChange={(e) => change("destination", e.target.value)}
                />
              </div>
            </label>
            <label className="search-field vehicle-filter">
              <span>{t("Transport turi")}</span>
              <div>
                <Truck size={17} />
                <select
                  aria-label={t("Transport turi")}
                  value={draft.vehicle}
                  onChange={(e) => change("vehicle", e.target.value)}
                >
                  <option value="">{t("Barcha transportlar")}</option>
                  <option value="tent">{t("Tent")}</option>
                  <option value="ref">{t("Refrigerator")}</option>
                  <option value="fura">{t("Fura")}</option>
                  <option value="bort">{t("Bortli")}</option>
                </select>
              </div>
            </label>
            <button className="button primary search-submit">
              <Search size={18} />
              {t("Yuk qidirish")}
            </button>
          </div>
          {advanced && (
            <div className="advanced-fields">
              <label className="field">
                <span>{t("Yuk nomi yoki yo‘nalish")}</span>
                <input
                  value={draft.search}
                  onChange={(e) => change("search", e.target.value)}
                  placeholder={t("Masalan, sement")}
                />
              </label>
              <label className="field">
                <span>{t("Maksimal og‘irlik (tonna)")}</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={draft.weight}
                  onChange={(e) => change("weight", e.target.value)}
                  placeholder={t("Masalan, 20")}
                />
              </label>
            </div>
          )}
        </form>
      </section>
      <div className="results-toolbar">
        <div className="results-title">
          <h2>{onlySaved ? t("Tanlangan e’lonlar") : t("Aktual yuklar")}</h2>
          <span className="count-badge">{visible.length}</span>
          {activeFilters && (
            <button className="text-button" onClick={reset}>
              {t("Tozalash")}
              <X size={14} />
            </button>
          )}
        </div>
        <div className="results-actions">
          <button
            className="icon-button"
            aria-label={t("Yuklarni yangilash")}
            onClick={() => void refresh()}
            disabled={loading}
          >
            <RefreshCw size={17} className={loading ? "spin" : ""} />
          </button>
          <select
            aria-label="Saralash"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
          >
            <option value="newest">{t("Eng yangilari")}</option>
            <option value="oldest">{t("Avval eskilari")}</option>
            <option value="weight">{t("Og‘irligi bo‘yicha")}</option>
          </select>
          <div className="view-toggle">
            <button
              aria-label={t("Kartochka ko‘rinishi")}
              aria-pressed={layout === "grid"}
              onClick={() => setLayout("grid")}
              className={layout === "grid" ? "selected" : ""}
            >
              <LayoutGrid size={17} />
            </button>
            <button
              aria-label={t("Ro‘yxat ko‘rinishi")}
              aria-pressed={layout === "list"}
              onClick={() => setLayout("list")}
              className={layout === "list" ? "selected" : ""}
            >
              <List size={18} />
            </button>
          </div>
        </div>
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : error ? (
        <Empty
          title={t("Yuklarni yuklab bo‘lmadi")}
          description={t(
            "Internet aloqasini tekshiring va qayta urinib ko‘ring.",
          )}
          action={
            <button className="button secondary" onClick={() => void refresh()}>
              {t("Qayta urinish")}
            </button>
          }
        />
      ) : visible.length === 0 ? (
        <Empty
          title={
            onlySaved
              ? t("Hozircha saqlangan yuk yo‘q")
              : t("Bu yo‘nalishda yuk topilmadi")
          }
          description={
            onlySaved
              ? t(
                  "Yuk kartasidagi saqlash belgisini bosing — e’lon shu yerda paydo bo‘ladi.",
                )
              : t(
                  "Filtrlarni o‘zgartiring yoki keyinroq yana tekshiring. Yangi e’lonlar shu yerda ko‘rinadi.",
                )
          }
          action={
            onlySaved ? (
              <Link href="/" className="button primary">
                {t("Yuklarni ko‘rish")}
                <ArrowRight size={17} />
              </Link>
            ) : activeFilters ? (
              <button className="button secondary" onClick={reset}>
                {t("Filtrlarni tozalash")}
              </button>
            ) : (
              <Link href="/loads/new" className="button primary">
                {t("Birinchi yukni joylash")}
              </Link>
            )
          }
        />
      ) : (
        <div className={`loads-grid ${layout === "list" ? "list-view" : ""}`}>
          {visible.slice((currentPage - 1) * 9, currentPage * 9).map((load) => (
            <LoadCard
              key={load.id}
              load={load}
              saved={saved.includes(load.id)}
              onSave={toggle}
            />
          ))}
        </div>
      )}
      {!loading && visible.length > 0 && (
        <div className="pagination">
          <span>
            {visible.length}
            {t("ta yukdan")}
            {(currentPage - 1) * 9 + 1}–
            {Math.min(currentPage * 9, visible.length)}
            {t("ko‘rsatilmoqda")}
          </span>
          <div>
            <button
              className="icon-button"
              disabled={currentPage === 1}
              aria-label={t("Oldingi sahifa")}
              onClick={() => setPage(currentPage - 1)}
            >
              <ChevronLeft size={18} />
            </button>
            <span>
              {currentPage} / {pages}
            </span>
            <button
              className="icon-button"
              disabled={currentPage === pages}
              aria-label={t("Keyingi sahifa")}
              onClick={() => setPage(currentPage + 1)}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
