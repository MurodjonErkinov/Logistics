"use client";
import { Clock3, ExternalLink, MapPinned } from "lucide-react";
import { useLocale } from "./locale";
import { yandexRouteUrls } from "@/lib/yandex-maps";

export function RouteMap({
  origin,
  destination,
  originPoint,
  destinationPoint,
  className = "",
}: {
  origin: string;
  destination: string;
  originPoint?: string;
  destinationPoint?: string;
  className?: string;
}) {
  const { t, locale } = useLocale();
  const { embed, external } = yandexRouteUrls(
    originPoint ?? origin,
    destinationPoint ?? destination,
    locale,
  );
  return (
    <section className={`route-map-panel ${className}`}>
      <div className="route-map-heading">
        <div>
          <span className="eyebrow">{t("YO‘NALISH XARITASI")}</span>
          <h2>
            <MapPinned size={21} />
            {origin} <span>→</span> {destination}
          </h2>
        </div>
        <a
          href={external}
          target="_blank"
          rel="noopener noreferrer"
          className="button secondary small-button"
        >
          {t("Xaritada ochish")}
          <ExternalLink size={15} />
        </a>
      </div>
      <div className="route-map-info">
        <Clock3 size={15} />
        {t("Yo‘l masofasi va taxminiy vaqtni xaritada ko‘ring.")}
      </div>
      <iframe
        key={embed}
        title={`${t("Yo‘nalish")}: ${origin} → ${destination}`}
        src={embed}
        loading="lazy"
        referrerPolicy="no-referrer"
        allowFullScreen
      />
      <p className="map-note">
        {t(
          "Manzillar e’londan olindi. Aniq yuklash joyi va yuk mashinasiga mos yo‘lni yuk egasi bilan tekshiring. Xarita ochilmasa, yuqoridagi havoladan foydalaning.",
        )}
      </p>
    </section>
  );
}
