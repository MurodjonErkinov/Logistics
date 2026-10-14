"use client";
import { useLocale } from "@/components/locale";
import Link from "next/link";
export default function NotFound() {
  const { t } = useLocale();

  return (
    <div className="empty">
      <span className="eyebrow">404</span>
      <h1>{t("Bu yo‘l topilmadi")}</h1>
      <p>{t("Sahifa manzili o‘zgargan yoki mavjud emas.")}</p>
      <Link href="/" className="button primary">
        {t("Yuklar birjasiga qaytish")}
      </Link>
    </div>
  );
}
