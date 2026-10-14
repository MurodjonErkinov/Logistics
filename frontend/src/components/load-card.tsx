"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Box,
  Building2,
  CalendarDays,
  Truck,
  Weight,
} from "lucide-react";
import type { Load } from "@/lib/types";
import { dateLabel, price } from "@/lib/api";

export function LoadCard({
  load,
  saved,
  onSave,
}: {
  load: Load;
  saved: boolean;
  onSave: (id: number) => void;
}) {
  const { t, locale } = useLocale();

  return (
    <article className="load-card">
      <div className="card-top">
        <span
          className={`status-chip ${load.status === "closed" ? "closed" : ""}`}
        >
          <span />
          {load.status === "open" ? t("Aktual yuk") : t("Yopilgan")}
        </span>
        <span className="card-date">{dateLabel(load.created_at, locale)}</span>
        <button
          className={`icon-button save-button ${saved ? "is-saved" : ""}`}
          onClick={() => onSave(load.id)}
          aria-label={
            saved ? t("Saqlanganlardan olib tashlash") : t("Yukni saqlash")
          }
          aria-pressed={saved}
        >
          <Bookmark size={19} fill={saved ? "currentColor" : "none"} />
        </button>
      </div>
      <Link href={`/loads/${load.id}`} className="card-route">
        <div>
          <span className="route-point origin" />
          <strong>{load.origin}</strong>
        </div>
        <span className="route-connector" />
        <div>
          <span className="route-point destination" />
          <strong>{load.destination}</strong>
        </div>
        <ArrowUpRight className="route-link-arrow" size={19} />
      </Link>
      <div className="cargo-title">
        <Box size={16} />
        <span>{load.cargo_name}</span>
      </div>
      <div className="load-specs">
        <span>
          <Truck size={15} />
          {load.vehicle_type}
        </span>
        <span>
          <Weight size={15} />
          {Number(load.weight_tons)} t
        </span>
        {load.pickup_date && (
          <span>
            <CalendarDays size={15} />
            {dateLabel(load.pickup_date, locale)}
          </span>
        )}
      </div>
      <div className="card-bottom">
        <div>
          <span className="price-label">{t("Tashish narxi")}</span>
          <strong className="load-price">{t(price(load, locale))}</strong>
        </div>
        <Link
          href={`/loads/${load.id}`}
          className="card-detail"
          aria-label={`${load.origin} — ${load.destination} yuk tafsilotlari`}
        >
          <ArrowRight size={20} />
        </Link>
      </div>
      <div className="card-source">
        <Building2 size={13} />
        <span>
          {load.company_name ||
            (load.source_url ? t("Telegram e’loni") : load.posted_by_username)}
        </span>
        {load.source_url && <span className="source-tag">Telegram</span>}
      </div>
    </article>
  );
}
