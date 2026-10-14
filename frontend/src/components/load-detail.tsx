"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Building2,
  CalendarDays,
  Check,
  MapPin,
  Package,
  Pencil,
  Phone,
  Share2,
  ShieldCheck,
  Truck,
  Weight,
} from "lucide-react";
import { api, dateLabel, errorMessage, price } from "@/lib/api";
import type { Company, Load } from "@/lib/types";
import { useSession } from "./session";
import { useSaved } from "./use-saved";
import { Empty, ErrorBox, Loading } from "./ui";

export function LoadDetail({ id }: { id: string }) {
  const { t, locale } = useLocale();

  const { user } = useSession();
  const [load, setLoad] = useState<Load | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const { saved, toggle } = useSaved();
  useEffect(() => {
    setLoading(true);
    api<Load>(`cargo/loads/${id}/`)
      .then(setLoad)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
    if (user)
      api<Company[]>("partners/companies/?mine=1")
        .then(setCompanies)
        .catch(() => {});
  }, [id, user?.id]);
  if (loading) return <Loading />;
  if (!load)
    return (
      <Empty
        title={t("Yuk topilmadi")}
        description={error || t("E’lon o‘chirilgan bo‘lishi mumkin.")}
        action={
          <Link href="/" className="button primary">
            {t("Yuklarga qaytish")}
          </Link>
        }
      />
    );
  const company = companies.find((c) => c.id === load.company);
  const manage =
    user &&
    (user.is_staff ||
      (!load.company && user.id === load.posted_by) ||
      company?.my_role === "owner" ||
      (company?.can_post_cargo && user.id === load.posted_by));
  return (
    <>
      <Link href="/" className="back-link">
        <ArrowLeft size={16} />
        {t("Yuklar birjasiga qaytish")}
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            {t("YUK #")}
            {load.id}
          </div>
          <h1>
            {load.origin} <span className="muted-arrow">→</span>{" "}
            {load.destination}
          </h1>
          <p>
            {dateLabel(load.created_at, locale)}
            {t("kuni joylangan ·")}{" "}
            {load.company_name || load.posted_by_username}
          </p>
        </div>
        <button
          className={`button secondary ${saved.includes(load.id) ? "saved" : ""}`}
          onClick={() => toggle(load.id)}
        >
          <Bookmark size={18} />
          {saved.includes(load.id) ? t("Saqlangan") : t("Saqlash")}
        </button>
      </div>
      <ErrorBox message={error} />
      <div className="detail-layout">
        <div>
          <section className="detail-main panel">
            <div className="detail-top">
              <span
                className={`status-chip ${load.status === "closed" ? "closed" : ""}`}
              >
                <span />
                {load.status === "open" ? t("Aktual yuk") : t("E’lon yopilgan")}
              </span>
              <span className="muted">#{load.id}</span>
            </div>
            <div className="detail-route">
              <div>
                <span className="route-point origin" />
                <small>{t("YUKLASH")}</small>
                <h2>{load.origin}</h2>
              </div>
              <div className="detail-route-line">
                <ArrowRight size={20} />
              </div>
              <div>
                <MapPin size={22} />
                <small>{t("TUSHIRISH")}</small>
                <h2>{load.destination}</h2>
              </div>
            </div>
            <div className="detail-specs">
              <div>
                <Package size={22} />
                <span>{t("Yuk turi")}</span>
                <strong>{load.cargo_name}</strong>
              </div>
              <div>
                <Truck size={22} />
                <span>{t("Transport")}</span>
                <strong>{load.vehicle_type}</strong>
              </div>
              <div>
                <Weight size={22} />
                <span>{t("Og‘irlik")}</span>
                <strong>
                  {Number(load.weight_tons)}
                  {t("tonna")}
                </strong>
              </div>
              <div>
                <CalendarDays size={22} />
                <span>{t("Yuklash sanasi")}</span>
                <strong>
                  {load.pickup_date
                    ? dateLabel(load.pickup_date, locale)
                    : t("Aniqlashtiriladi")}
                </strong>
              </div>
            </div>
            {load.notes && (
              <div className="detail-notes">
                <h3>{t("Qo‘shimcha ma’lumot")}</h3>
                <p>{load.notes}</p>
              </div>
            )}
            <div className="detail-actions">
              {manage && (
                <Link
                  href={`/loads/${load.id}/edit`}
                  className="button secondary"
                >
                  <Pencil size={16} />
                  {t("Tahrirlash")}
                </Link>
              )}
              <button
                className="button secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(window.location.href);
                    setCopied(true);
                  } catch {
                    setError(
                      t(
                        "Havolani nusxalash imkoni bo‘lmadi. Manzil satridan nusxa oling.",
                      ),
                    );
                  }
                }}
              >
                {copied ? <Check size={16} /> : <Share2 size={16} />}
                {copied ? t("Havola nusxalandi") : t("Ulashish")}
              </button>
              {load.source_url && (
                <a
                  className="text-button"
                  href={load.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("Telegramdagi e’lon")}
                  <ArrowUpRight size={15} />
                </a>
              )}
            </div>
          </section>
        </div>
        <aside>
          <section className="contact-panel panel">
            <span className="eyebrow">{t("TASHISH NARXI")}</span>
            <h2>{t(price(load, locale))}</h2>
            {load.price_amount && load.is_price_negotiable && (
              <p className="muted">{t("Narxni kelishish mumkin")}</p>
            )}
            <div className="contact-owner">
              <span className="avatar">
                <Building2 size={20} />
              </span>
              <div>
                <strong>{load.company_name || load.posted_by_username}</strong>
                <small>
                  {load.company
                    ? t("Kompaniya")
                    : load.source_url
                      ? t("Telegram e’loni")
                      : t("Yuk jo‘natuvchi")}
                </small>
              </div>
            </div>
            {load.status === "closed" ? (
              <p className="notice">
                {t("Bu yuk e’loni yopilgan. Boshqa aktual yuklarni ko‘ring.")}
              </p>
            ) : user ? (
              <div className="form-stack">
                <a
                  className="button primary full-width"
                  href={`tel:${load.contact_phone}`}
                >
                  <Phone size={18} />
                  {load.contact_phone}
                </a>
                {load.alternate_phone && (
                  <a
                    className="button secondary full-width"
                    href={`tel:${load.alternate_phone}`}
                  >
                    <Phone size={18} />
                    {load.alternate_phone}
                  </a>
                )}
              </div>
            ) : (
              <>
                <p className="contact-hint">
                  {t("Telefon raqamini ko‘rish uchun akkauntingizga kiring.")}
                </p>
                <Link
                  href={`/login?next=/loads/${id}`}
                  className="button primary full-width"
                >
                  {t("Kirish va bog‘lanish")}
                  <ArrowRight size={17} />
                </Link>
              </>
            )}
            <div className="contact-note">
              <ShieldCheck size={17} />
              <p>
                {t(
                  "Yo‘lga chiqishdan oldin yuk hali aktual ekanini telefon orqali tasdiqlang.",
                )}
              </p>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
