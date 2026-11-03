"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  Clock3,
  MapPin,
  Package,
  Search,
  Truck,
  Users,
} from "lucide-react";
import { api, dateLabel, errorMessage, price } from "@/lib/api";
import type { Load } from "@/lib/types";
import { DriverOnly } from "./driver-tools";
import { useLocale } from "./locale";
import { Empty, ErrorBox, Loading } from "./ui";

export function DriverLoads() {
  return (
    <DriverOnly>
      <TakenLoads />
    </DriverOnly>
  );
}

function TakenLoads() {
  const { t, locale } = useLocale();
  const [loads, setLoads] = useState<Load[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const data = await api<Load[]>("cargo/loads/?claimed=1");
        if (active) {
          setLoads(data);
          setError("");
        }
      } catch (e) {
        if (active) setError(errorMessage(e));
      } finally {
        if (active) setLoading(false);
      }
    }
    void refresh();
    const interval = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 20000);
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
    };
  }, []);
  const open = loads.filter((l) => l.status === "open").length;
  const visible = loads.filter(
    (l) =>
      (filter === "all" || l.status === filter) &&
      `${l.origin} ${l.destination} ${l.cargo_name}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <div className="driver-loads-page">
      <section className="haul-hero">
        <div className="haul-hero-copy">
          <span className="haul-eyebrow">
            <Truck size={15} /> {t("HAYDOVCHI UCHUN")}
          </span>
          <h1>{t("Mening yuklarim")}</h1>
          <p>
            {t(
              "Kelishilgan yuklar, barcha manzillar va aloqa ma’lumotlari — bir joyda.",
            )}
          </p>
          <Link href="/" className="button haul-hero-button">
            {t("Yangi yuk topish")} <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="haul-hero-visual" aria-hidden="true">
          <span className="haul-orbit orbit-one" />
          <span className="haul-orbit orbit-two" />
          <div className="haul-route-stamp">
            <MapPin size={20} />
            <span>{t("Yo‘lingiz ochiq bo‘lsin")}</span>
            <ArrowRight size={18} />
          </div>
          <div className="haul-hero-truck">
            <Truck size={62} strokeWidth={1.2} />
          </div>
        </div>
      </section>
      <div className="haul-stats">
        <div>
          <span className="haul-stat-icon">
            <Package size={21} />
          </span>
          <span>
            {t("Olingan yuklar")}
            <strong>{loads.length}</strong>
          </span>
        </div>
        <div>
          <span className="haul-stat-icon">
            <Truck size={21} />
          </span>
          <span>
            {t("Aktual e’lonlar")}
            <strong>{open}</strong>
          </span>
        </div>
        <div>
          <span className="haul-stat-icon">
            <CheckCheck size={21} />
          </span>
          <span>
            {t("Yopilgan e’lonlar")}
            <strong>{loads.length - open}</strong>
          </span>
        </div>
      </div>
      <div className="haul-list-heading">
        <div>
          <h2>{t("Siz olgan yuklar")}</h2>
          <p>
            <span className="haul-live-dot" />
            {t("Ma’lumotlar avtomatik yangilanadi")}
          </p>
        </div>
        <label className="haul-search">
          <Search size={18} />
          <input
            aria-label={t("Yuklarimdan qidirish")}
            placeholder={t("Manzil yoki yuk nomi…")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      <div className="tabs">
        {[
          ["all", "Barchasi"],
          ["open", "Aktual"],
          ["closed", "Yopilgan"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => setFilter(value)}
          >
            {t(label)}
          </button>
        ))}
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : !visible.length ? (
        <Empty
          title={t(
            loads.length ? "Yuk topilmadi" : "Birinchi yukingizni oling",
          )}
          description={t(
            loads.length
              ? "Boshqa manzil yoki filtr bilan qidirib ko‘ring."
              : "Yuk egasi bilan kelishing va e’londagi «Yukni olish» tugmasini bosing. Yuk shu yerda paydo bo‘ladi.",
          )}
          action={
            <Link href="/" className="button primary">
              {t("Yuklarni ko‘rish")}
              <ArrowRight size={17} />
            </Link>
          }
        />
      ) : (
        <div className="haul-grid">
          {visible.map((load) => (
            <Link
              href={`/loads/${load.id}`}
              className="haul-card"
              key={load.id}
            >
              <div className="haul-card-top">
                <span
                  className={`status-chip ${load.status === "closed" ? "closed" : ""}`}
                >
                  <span />
                  {t(load.status === "open" ? "Aktual yuk" : "E’lon yopilgan")}
                </span>
                <span className="haul-id">#{load.id}</span>
              </div>
              <div className="haul-card-route">
                <div>
                  <span className="haul-route-dot" />
                  <small>{t("Qayerdan")}</small>
                  <strong>{load.origin}</strong>
                </div>
                <div>
                  <MapPin size={16} />
                  <small>{t("Qayerga")}</small>
                  <strong>{load.destination}</strong>
                </div>
              </div>
              <div className="haul-card-specs">
                <span>
                  <Package size={15} />
                  {load.cargo_name}
                </span>
                <span>
                  <Truck size={15} />
                  {load.vehicle_type} · {Number(load.weight_tons)} t
                </span>
              </div>
              <div className="haul-card-price">
                <strong>{t(price(load, locale))}</strong>
                <span>
                  <Clock3 size={14} />
                  {load.claimed_at ? dateLabel(load.claimed_at, locale) : ""}
                </span>
              </div>
              <div className="haul-card-footer">
                <span>
                  <Users size={16} />
                  <b>{Math.max(0, (load.claim_count ?? 1) - 1)}</b>{" "}
                  {t("boshqa haydovchi olgan")}
                </span>
                <span className="haul-open-arrow">
                  <ArrowUpRight size={20} />
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
