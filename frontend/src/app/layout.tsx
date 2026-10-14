import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LocaleProvider } from "@/components/locale";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import "./globals.css";
import { SessionProvider } from "@/components/session";
import { Shell } from "@/components/shell";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const russian = (await cookies()).get("yf_locale")?.value === "ru";
  return {
    title: {
      default: russian
        ? "YukFlow — Грузы по вашему маршруту"
        : "YukFlow — Yo‘lingizga mos yuk",
      template: "%s · YukFlow",
    },
    description: russian
      ? "Находите актуальные грузы и размещайте объявления от себя или компании."
      : "Aktual yuklarni toping, shaxsiy yoki kompaniya nomidan yuk joylang.",
  };
}
export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const locale =
    (await cookies()).get("yf_locale")?.value === "ru" ? "ru" : "uz";
  return (
    <html lang={locale} data-scroll-behavior="smooth">
      <body>
        <LocaleProvider initialLocale={locale}>
          <SessionProvider>
            <Shell>{children}</Shell>
          </SessionProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
