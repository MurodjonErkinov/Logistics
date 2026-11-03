"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, MapPin, Navigation } from "lucide-react";
import type { Load } from "@/lib/types";
import { useLocale } from "./locale";
import { api } from "@/lib/api";

type MapPoint = {
  lat: number;
  lon: number;
  approximate: boolean;
  label: string;
};

export function LoadRouteMap({ load }: { load: Load }) {
  const { t } = useLocale();
  const [point, setPoint] = useState<"origin" | "destination">("origin");
  const [locations, setLocations] = useState<{
    origin?: MapPoint | null;
    destination?: MapPoint | null;
  }>({});
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setLocations({});
    api<{ origin: MapPoint | null; destination: MapPoint | null }>(
      `cargo/loads/${load.id}/map-locations/`,
    )
      .then((data) => {
        if (active) setLocations(data);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    load.id,
    load.origin,
    load.destination,
    load.origin_lat,
    load.origin_lon,
    load.destination_lat,
    load.destination_lon,
  ]);
  const coordinates = (key: "origin" | "destination") =>
    load[`${key}_lat`] != null && load[`${key}_lon`] != null
      ? `${load[`${key}_lat`]},${load[`${key}_lon`]}`
      : load[key];
  const location = locations[point];
  const span = location?.approximate ? 0.12 : 0.01;
  const bbox = location
    ? [
        Math.max(-180, location.lon - span),
        Math.max(-90, location.lat - span),
        Math.min(180, location.lon + span),
        Math.min(90, location.lat + span),
      ].join(",")
    : "";
  const directions = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(coordinates("origin"))}&destination=${encodeURIComponent(coordinates("destination"))}&travelmode=driving`;
  const precise = location && !location.approximate;
  return (
    <section className="route-map-panel load-route-map-panel panel">
      <div className="route-map-heading">
        <div>
          <span className="eyebrow">{t("MANZILLAR XARITADA")}</span>
          <h3>{t("Yo‘nalishni ko‘rib chiqing")}</h3>
        </div>
        <Navigation size={24} />
      </div>
      <div
        className="route-map-tabs"
        role="tablist"
        aria-label={t("Xaritadagi manzil")}
      >
        {(["origin", "destination"] as const).map((key) => (
          <button
            key={key}
            id={`map-tab-${key}`}
            role="tab"
            aria-selected={point === key}
            aria-controls="load-map"
            className={point === key ? "active" : ""}
            onClick={() => setPoint(key)}
          >
            <MapPin size={16} />
            <span>
              <small>{t(key === "origin" ? "Yuklash" : "Tushirish")}</small>
              {load[key]}
            </span>
          </button>
        ))}
      </div>
      <div
        id="load-map"
        className="load-map"
        role="tabpanel"
        aria-labelledby={`map-tab-${point}`}
      >
        {location ? (
          <iframe
            key={`${location.lat},${location.lon}`}
            title={`${t("Manzil xaritasi")}: ${load[point]}`}
            src={`https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${location.lat},${location.lon}`}
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            allowFullScreen
          />
        ) : (
          <div className="map-unavailable">
            <MapPin size={30} />
            <p>
              {t(
                loading
                  ? "Manzil xaritada qidirilmoqda…"
                  : "Ichki xarita hozir ochilmadi. «Yo‘lni ochish» orqali xaritani ko‘ring.",
              )}
            </p>
          </div>
        )}
      </div>
      <div className="route-map-footer">
        <p>
          {t(
            precise
              ? "E’londa ko‘rsatilgan koordinata."
              : "Xaritada shahar ko‘rsatilgan. Aniq manzilni yuk egasidan oling.",
          )}
          {location?.approximate && (
            <>
              <br />
              {location.label}
            </>
          )}
        </p>
        <a href={directions} target="_blank" rel="noopener noreferrer">
          {t("Yo‘lni ochish")}
          <ArrowUpRight size={16} />
        </a>
      </div>
    </section>
  );
}
