"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Route,
  Truck,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { api, errorMessage } from "@/lib/api";
import { useSession } from "./session";
import { ErrorBox, Field } from "./ui";
import { RegistrationPhone } from "./registration-phone";

export function AuthForm({ register = false }: { register?: boolean }) {
  const { t } = useLocale();

  const router = useRouter();
  const { reload } = useSession();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const [continuation, setContinuation] = useState("");
  const [role, setRole] = useState("dispatcher");
  useEffect(() => {
    const next = new URLSearchParams(window.location.search).get("next");
    if (next?.startsWith("/") && !next.startsWith("//") && !next.includes("\\"))
      setContinuation(`?next=${encodeURIComponent(next)}`);
    const requestedRole = new URLSearchParams(window.location.search).get(
      "role",
    );
    if (requestedRole === "driver" || requestedRole === "dispatcher")
      setRole(requestedRole);
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (register && !data.verification_id)
        throw new Error(
          t("Avval telefon raqamingizni Telegram orqali tasdiqlang."),
        );
      if (register)
        await api("auth/register/", {
          method: "POST",
          body: JSON.stringify(data),
        });
      await api("auth/login/", {
        method: "POST",
        body: JSON.stringify({
          username: data.username,
          password: data.password,
        }),
      });
      const user = await reload();
      const next = new URLSearchParams(window.location.search).get("next");
      const safe =
        next?.startsWith("/") && !next.startsWith("//") && !next.includes("\\");
      router.replace(
        safe
          ? next!
          : user?.is_staff
            ? "/admin"
            : user?.role === "driver"
              ? "/driver"
              : "/dashboard",
      );
      router.refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="auth-story">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <Route size={25} />
          </span>
          yukflow<span className="brand-dot">.</span>
        </Link>
        <div className="auth-story-content">
          <span className="hero-kicker">{t("YO‘LLARIMIZ BIRLASHADI")}</span>
          <h1>
            {t("Yukingiz bor.")}
            <br />
            {t("Yo‘lingiz bor.")}
            <br />
            <em>{t("YukFlow bor.")}</em>
          </h1>
          <p>
            {t(
              "Haydovchilar, yuk jo‘natuvchilar va kompaniyalar uchun bitta qulay platforma.",
            )}
          </p>
          <div className="auth-benefits">
            <span>
              <Check size={17} />
              {t("Yo‘nalishga mos yuklar")}
            </span>
            <span>
              <Check size={17} />
              {t("Yuk beruvchi bilan bevosita aloqa")}
            </span>
            <span>
              <Check size={17} />
              {t("Shaxsiy va kompaniya kabineti")}
            </span>
          </div>
        </div>
        <div className="auth-story-foot">
          <Truck size={24} />
          <span>{t("Har bir yukni o‘z manziliga.")}</span>
        </div>
      </section>
      <section className="auth-form-side">
        <Link href="/" className="back-link">
          <ArrowLeft size={16} />
          {t("Yuklar birjasiga qaytish")}
        </Link>
        <div className="auth-form-wrap">
          <span className="eyebrow">
            {register
              ? t("BIRINCHI QADAM")
              : t("YANA KO‘RISHGANIMIZDAN XURSANDMIZ")}
          </span>
          <h2>{register ? t("Akkaunt yarating") : t("Xush kelibsiz")}</h2>
          <p>
            {register
              ? t("Yuk joylang, kerakli yo‘nalishlarni toping.")
              : t("Ishingizni davom ettirish uchun akkauntingizga kiring.")}
          </p>
          <ErrorBox message={error} />
          <form onSubmit={submit} className="form-stack">
            {register && (
              <Field label={t("Rol")}>
                <select
                  name="role"
                  required
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                >
                  <option value="dispatcher">
                    {t("Dispetcher")} — {t("Yuk joylash")}
                  </option>
                  <option value="driver">{t("Haydovchi")}</option>
                </select>
              </Field>
            )}
            {register && (
              <div className="form-row">
                <Field label={t("Ism")}>
                  <input
                    name="first_name"
                    autoComplete="given-name"
                    required
                    maxLength={150}
                  />
                </Field>
                <Field label={t("Familiya")}>
                  <input
                    name="last_name"
                    autoComplete="family-name"
                    maxLength={150}
                  />
                </Field>
              </div>
            )}
            <Field label={t("Foydalanuvchi nomi")}>
              <input
                name="username"
                autoComplete="username"
                required
                maxLength={150}
                placeholder={t("Foydalanuvchi nomingiz")}
              />
            </Field>
            {register && <RegistrationPhone disabled={busy} />}
            <Field
              label={t("Parol")}
              hint={
                register
                  ? t("Kamida 8 belgi. Faqat raqamlardan iborat bo‘lmasin.")
                  : undefined
              }
            >
              <div className="password-field">
                <input
                  name="password"
                  type={show ? "text" : "password"}
                  autoComplete={register ? "new-password" : "current-password"}
                  minLength={register ? 8 : undefined}
                  required
                  placeholder={t("Parolingizni kiriting")}
                />
                <button
                  className="icon-button"
                  type="button"
                  onClick={() => setShow(!show)}
                  aria-label={
                    show ? t("Parolni yashirish") : t("Parolni ko‘rsatish")
                  }
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </Field>
            <button className="button primary full-width" disabled={busy}>
              {busy
                ? t("Kutilmoqda…")
                : register
                  ? t("Akkaunt yaratish")
                  : t("Kirish")}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="auth-switch">
            {register
              ? t("Akkauntingiz bormi?")
              : t("Hali akkauntingiz yo‘qmi?")}{" "}
            <Link href={`${register ? "/login" : "/register"}${continuation}`}>
              {register ? t("Kirish") : t("Ro‘yxatdan o‘tish")}
            </Link>
          </p>
        </div>
        <span className="auth-copyright">
          © {new Date().getFullYear()}
          {t("YukFlow. Yo‘lingiz ochiq bo‘lsin.")}
        </span>
      </section>
    </>
  );
}
