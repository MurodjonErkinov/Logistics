"use client";
import { ExternalLink, MapPinned } from "lucide-react";
import { useLocale } from "./locale";

export function RouteMap({
  origin,
  destination,
}: {
  origin: string;
  destination: string;
}) {
  const { t, locale } = useLocale();
  const params = new URLSearchParams({
    rtext: `${origin.replaceAll("~", " ")}~${destination.replaceAll("~", " ")}`,
    rtt: "auto",
    mode: "routes",
    lang: locale === "ru" ? "ru_RU" : "en_US",
  });
  const route = `https://yandex.com/maps/?${params}`;
  return (
    <section className="route-map-panel">
      <div className="route-map-heading">
        <div>
          <span className="eyebrow">{t("YO‘NALISH XARITASI")}</span>
          <h2>
            <MapPinned size={21} />
            {origin} <span>→</span> {destination}
          </h2>
        </div>
        <a
          href={route}
          target="_blank"
          rel="noopener noreferrer"
          className="button secondary small-button"
        >
          {t("Xaritada ochish")}
          <ExternalLink size={15} />
        </a>
      </div>
      <iframe
        key={`${origin}-${destination}-${locale}`}
        title={`${t("Yo‘nalish")}: ${origin} → ${destination}`}
        src={`https://yandex.com/map-widget/v1/?${params}`}
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
