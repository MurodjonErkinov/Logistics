"use client";
import { useLocale } from "@/components/locale";
export default function ErrorPage({ reset }: { reset: () => void }) {
  const { t } = useLocale();

  return (
    <div className="empty">
      <h2>{t("Sahifani ochib bo‘lmadi")}</h2>
      <p>{t("Qayta urinib ko‘ring.")}</p>
      <button className="button primary" onClick={reset}>
        {t("Qayta yuklash")}
      </button>
    </div>
  );
}
