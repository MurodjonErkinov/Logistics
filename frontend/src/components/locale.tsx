"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { cookiePath } from "@/lib/paths";
import russian from "@/i18n/ru.json";
export type Locale = "uz" | "ru";
const dictionary: Record<string, string> = russian;
const uzbek: Record<string, string> = {
  active: "Faol",
  paused: "Pauzada",
  closed: "Yopilgan",
  expired: "Muddati tugagan",
  tent: "Tent",
  refrigerator: "Refrijerator",
  flatbed: "Bort / platforma",
  van: "Furgon",
  tanker: "Sisterna",
  other: "Boshqa",
  isothermal: "Izotermik",
  dump: "Samosval",
  lowbed: "Tral",
  container: "Konteyner",
};
const Context = createContext({
  locale: "uz" as Locale,
  setLocale: (_locale: Locale) => {},
  t: (text: string) => text,
});
export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const [locale, update] = useState(initialLocale);
  const setLocale = useCallback((value: Locale) => {
    update(value);
    document.documentElement.lang = value;
    document.title =
      value === "ru"
        ? "YukFlow — Грузы по вашему маршруту"
        : "YukFlow — Yo‘lingizga mos yuk";
    document.cookie = `yf_locale=${value}; Path=${cookiePath}; Max-Age=31536000; SameSite=Lax${window.location.protocol === "https:" ? "; Secure" : ""}`;
  }, []);
  const t = useCallback(
    (text: string) =>
      locale === "ru" ? dictionary[text] || text : uzbek[text] || text,
    [locale],
  );
  return (
    <Context.Provider value={{ locale, setLocale, t }}>
      {children}
    </Context.Provider>
  );
}
export const useLocale = () => useContext(Context);
export function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();
  return (
    <select
      className="language-select"
      aria-label="Til / Язык"
      value={locale}
      onChange={(event) => setLocale(event.target.value as Locale)}
    >
      <option value="uz">UZ · O‘zbekcha</option>
      <option value="ru">RU · Русский</option>
    </select>
  );
}
