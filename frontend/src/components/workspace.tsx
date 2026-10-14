"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownUp,
  ArrowUpRight,
  Bookmark,
  Building2,
  MapPinned,
  Package,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Truck,
} from "lucide-react";
import { api, dateLabel, errorMessage, price } from "@/lib/api";
import type { Load } from "@/lib/types";
import { useSession } from "./session";
import { useLocale } from "./locale";
import { useSaved } from "./use-saved";
import { Empty, ErrorBox, Field, Loading, Protected } from "./ui";
import { RouteMap } from "./route-map";

export function Workspace() {
  return (
    <Protected>
      <WorkspaceContent />
    </Protected>
  );
}
function WorkspaceContent() {
  const { user } = useSession();
  const { t, locale } = useLocale();
  const driver = user?.role === "driver";
  const { saved, toggle } = useSaved();
  const [loads, setLoads] = useState<Load[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [weight, setWeight] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [onlySaved, setOnlySaved] = useState(false);
  const [selection, setSelection] = useState<number | null>(null);
  const [limit, setLimit] = useState(12);
  const inFlight = useRef(false);
  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const data = await api<Load[]>(
        driver ? "cargo/loads/?status=open" : "cargo/loads/?mine=1",
      );
      setLoads(data);
      setUpdated(new Date());
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, [driver]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 60000);
    return () => clearInterval(timer);
  }, [refresh]);
  const visible = useMemo(
    () =>
      loads
        .filter((load) => {
          const match = (value: string, query: string) =>
            value
              .toLocaleLowerCase()
              .includes(query.trim().toLocaleLowerCase());
          return (
            match(load.origin, origin) &&
            match(load.destination, destination) &&
            match(load.vehicle_type, vehicle) &&
            (!weight || Number(load.weight_tons) <= Number(weight)) &&
            (!onlySaved || saved.includes(load.id))
          );
        })
        .sort((a, b) => b.id - a.id),
    [loads, origin, destination, weight, vehicle, onlySaved, saved],
  );
  const selected = visible.find((load) => load.id === selection) || visible[0];
  useEffect(
    () => setLimit(12),
    [origin, destination, weight, vehicle, onlySaved],
  );
  return (
    <div className="workspace-page">
      <section className="workspace-hero">
        <div>
          <span className="hero-kicker">
            {t(driver ? "HAYDOVCHI KABINETI" : "ISH KABINETI")}
          </span>
          <h1>
            {t("Salom")}, {user?.first_name || user?.username}
            <span>.</span>
          </h1>
          <p>
            {t(
              driver
                ? "Keyingi manzilingizni tanlang. Yo‘lingizga mos yuk shu yerda."
                : "Yuklaringiz, yo‘nalishlaringiz va kompaniyangiz — bir joyda.",
            )}
          </p>
          <div className="workspace-hero-actions">
            <Link
              className="button primary"
              href={driver ? "/saved" : "/loads/new"}
            >
              {driver ? <Bookmark size={17} /> : <Plus size={17} />}{" "}
              {t(driver ? "Saqlangan yuklar" : "Yuk joylash")}
            </Link>
            <Link
              className="workspace-hero-link"
              href={driver ? "/" : "/companies"}
            >
              {t(driver ? "Barcha yuklar" : "Kompaniyalarim")}
              <ArrowUpRight size={17} />
            </Link>
          </div>
        </div>
        <div className="workspace-illustration" aria-hidden="true">
          <span>A</span>
          <div className="workspace-road">
            <Truck size={49} />
          </div>
          <span>B</span>
        </div>
      </section>
      <div className="workspace-stats">
        <div>
          <Package />
          <span>{t(driver ? "Aktual yuklar" : "Mening yuklarim")}</span>
          <strong>{loading ? "—" : loads.length}</strong>
        </div>
        <div>
          <MapPinned />
          <span>{t("Yo‘nalishlar")}</span>
          <strong>
            {loading
              ? "—"
              : new Set(loads.map((l) => `${l.origin}→${l.destination}`)).size}
          </strong>
        </div>
        <div>
          <Bookmark />
          <span>
            {t(driver ? "Saqlangan aktual yuklar" : "Ochiq e’lonlar")}
          </span>
          <strong>
            {loading
              ? "—"
              : loads.filter((l) =>
                  driver ? saved.includes(l.id) : l.status === "open",
                ).length}
          </strong>
        </div>
      </div>
      {!driver && (
        <div className="workspace-shortcuts">
          <Link href="/my-loads">
            <Package />
            {t("E’lonlarni boshqarish")}
            <ArrowUpRight />
          </Link>
          <Link href="/companies">
            <Building2 />
            {t("Kompaniya va jamoa")}
            <ArrowUpRight />
          </Link>
        </div>
      )}
      <section className="workspace-filters">
        <div className="workspace-section-heading">
          <h2>
            <Search size={20} />
            {t(driver ? "Yo‘lingizga mos yuk" : "E’lonlaringiz xaritada")}
          </h2>
          <button
            type="button"
            className="button secondary small-button"
            disabled={loading}
            onClick={() => void refresh()}
          >
            <RefreshCw size={15} />
            {t("Yangilash")}
          </button>
        </div>
        <div className="workspace-filter-fields">
          <Field label={t("Qayerdan")}>
            <input
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              placeholder={t("Shahar yoki viloyat")}
            />
          </Field>
          <button
            className="icon-button swap-route"
            aria-label={t("Yo‘nalishni almashtirish")}
            onClick={() => {
              setOrigin(destination);
              setDestination(origin);
            }}
          >
            <ArrowDownUp size={19} />
          </button>
          <Field label={t("Qayerga")}>
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder={t("Shahar yoki viloyat")}
            />
          </Field>
          <Field label={t("Transport turi")}>
            <input
              value={vehicle}
              onChange={(e) => setVehicle(e.target.value)}
              placeholder={t("Masalan: tent")}
            />
          </Field>
          <Field label={t("Eng ko‘p og‘irlik (t)")}>
            <input
              type="number"
              min="0.1"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="20"
            />
          </Field>
        </div>
        <div className="workspace-filter-foot">
          <label>
            <input
              type="checkbox"
              checked={onlySaved}
              onChange={(e) => setOnlySaved(e.target.checked)}
            />
            {t("Faqat saqlanganlar")}
          </label>
          <button
            className="text-button"
            onClick={() => {
              setOrigin("");
              setDestination("");
              setVehicle("");
              setWeight("");
              setOnlySaved(false);
            }}
          >
            {t("Filtrlarni tozalash")}
          </button>
          <small>
            {updated
              ? `${t("Yangilangan")}: ${updated.toLocaleTimeString(locale === "ru" ? "ru-RU" : "uz-UZ", { hour: "2-digit", minute: "2-digit" })}`
              : ""}
          </small>
        </div>
      </section>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : !visible.length ? (
        <Empty
          title={t("Yuk topilmadi")}
          description={t("Filtrlarni o‘zgartiring yoki keyinroq tekshiring.")}
        />
      ) : (
        <div className="workspace-grid">
          <section className="workspace-results">
            <div className="workspace-section-heading">
              <h2>
                {t("Yuklar")}{" "}
                <span className="workspace-count">{visible.length}</span>
              </h2>
              <span>{t("Yangilari avval")}</span>
            </div>
            {visible.slice(0, limit).map((load) => (
              <article
                key={load.id}
                className={`workspace-load ${selected?.id === load.id ? "selected" : ""}`}
              >
                <div className="card-top">
                  <span
                    className={`status-chip ${load.status === "closed" ? "closed" : ""}`}
                  >
                    <span />
                    {t(load.status === "open" ? "Aktual yuk" : "Yopilgan")}
                  </span>
                  <span className="card-date">
                    {dateLabel(load.created_at, locale)}
                  </span>
                  <button
                    className={`icon-button ${saved.includes(load.id) ? "is-saved" : ""}`}
                    aria-label={t(
                      saved.includes(load.id)
                        ? "Saqlanganlardan olib tashlash"
                        : "Yukni saqlash",
                    )}
                    aria-pressed={saved.includes(load.id)}
                    onClick={() => toggle(load.id)}
                  >
                    <Bookmark
                      size={18}
                      fill={saved.includes(load.id) ? "currentColor" : "none"}
                    />
                  </button>
                </div>
                <button
                  className="workspace-load-route"
                  aria-pressed={selected?.id === load.id}
                  onClick={() => setSelection(load.id)}
                >
                  <strong>
                    {load.origin} <span>→</span> {load.destination}
                  </strong>
                  <MapPinned size={19} />
                </button>
                <p>{load.cargo_name}</p>
                <div className="workspace-load-meta">
                  <span>
                    <Truck size={15} />
                    {load.vehicle_type}
                  </span>
                  <span>{Number(load.weight_tons)} t</span>
                  <strong>{t(price(load, locale))}</strong>
                </div>
              </article>
            ))}
            {visible.length > limit && (
              <button
                className="button secondary full-width"
                onClick={() => setLimit((n) => n + 12)}
              >
                {t("Yana ko‘rsatish")}
              </button>
            )}
          </section>
          {selected && (
            <div className="workspace-map-column">
              <RouteMap
                origin={selected.origin}
                destination={selected.destination}
              />
              <section className="workspace-contact">
                <div>
                  <span className="eyebrow">{t("TANLANGAN YUK")}</span>
                  <h2>{selected.cargo_name}</h2>
                  <p>
                    {selected.company_name || selected.posted_by_username}
                    {selected.pickup_date
                      ? ` · ${dateLabel(selected.pickup_date, locale)}`
                      : ""}
                  </p>
                </div>
                <strong className="workspace-price">
                  {t(price(selected, locale))}
                </strong>
                <div className="workspace-contact-actions">
                  {selected.contact_phone && (
                    <a
                      className="button primary"
                      href={`tel:${selected.contact_phone}`}
                    >
                      <Phone size={17} />
                      {t("Qo‘ng‘iroq qilish")}
                    </a>
                  )}
                  <Link
                    className="button secondary"
                    href={`/loads/${selected.id}`}
                  >
                    {t("Yuk tafsilotlari")}
                    <ArrowUpRight size={17} />
                  </Link>
                </div>
                <p className="map-note">
                  {t(
                    "Yukning hali bo‘shligi va tashish shartlarini yuk egasi bilan kelishing. Saqlash yukni sizga band qilmaydi.",
                  )}
                </p>
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
