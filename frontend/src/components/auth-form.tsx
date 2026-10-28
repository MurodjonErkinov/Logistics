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

export function AuthForm({
  register = false,
  reset = false,
}: {
  register?: boolean;
  reset?: boolean;
}) {
  const { t } = useLocale();

  const router = useRouter();
  const { reload } = useSession();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const [done, setDone] = useState(false);
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
      if ((register || reset) && !data.verification_id)
        throw new Error(
          t(
            reset
              ? "Avval Telegramdan parolni tiklash kodini oling."
              : "Avval telefon raqamingizni Telegram orqali tasdiqlang.",
          ),
        );
      if (reset) {
        if (data.password !== data.password_confirm)
          throw new Error(t("Parollar bir xil bo‘lishi kerak."));
        await api("auth/reset-password/", {
          method: "POST",
          body: JSON.stringify(data),
        });
        await reload();
        setDone(true);
        return;
      }
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
  const usernameField = (
    <Field label={t("Foydalanuvchi nomi")}>
      <input
        name="username"
        autoComplete="username"
        required
        maxLength={150}
        placeholder={t("Foydalanuvchi nomingiz")}
      />
    </Field>
  );
  const passwordField = (
    <Field
      label={t(reset ? "Yangi parol" : "Parol")}
      hint={
        register || reset
          ? t("Kamida 8 belgi. Faqat raqamlardan iborat bo‘lmasin.")
          : undefined
      }
    >
      <div className="password-field">
        <input
          name="password"
          type={show ? "text" : "password"}
          autoComplete={register || reset ? "new-password" : "current-password"}
          minLength={register || reset ? 8 : undefined}
          maxLength={reset ? 128 : undefined}
          required
          placeholder={t("Parolingizni kiriting")}
        />
        <button
          className="icon-button"
          type="button"
          onClick={() => setShow(!show)}
          aria-label={show ? t("Parolni yashirish") : t("Parolni ko‘rsatish")}
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </Field>
  );
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
            {t("Yukingiz bor.")} <br />
            {t("Yo‘lingiz bor.")} <br />
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
            {reset
              ? t("AKKAUNTINGIZGA QAYTING")
              : register
                ? t("BIRINCHI QADAM")
                : t("YANA KO‘RISHGANIMIZDAN XURSANDMIZ")}
          </span>
          <h2>
            {reset
              ? t(done ? "Parolingiz yangilandi" : "Parolni tiklash")
              : register
                ? t("Akkaunt yarating")
                : t("Xush kelibsiz")}
          </h2>
          <p>
            {reset
              ? t(
                  done
                    ? "Endi yangi parol bilan akkauntingizga kirishingiz mumkin."
                    : "Telegramdan kod oling va akkauntingiz uchun yangi parol qo‘ying.",
                )
              : register
                ? t("Yuk joylang, kerakli yo‘nalishlarni toping.")
                : t("Ishingizni davom ettirish uchun akkauntingizga kiring.")}
          </p>
          <ErrorBox message={error} />
          {done ? (
            <>
              <div className="success-box" role="status">
                <Check size={20} />
                <span>
                  {t("Parol almashtirildi. Avvalgi sessiyalar yakunlandi.")}
                </span>
              </div>
              <Link
                href={`/login${continuation}`}
                className="button primary full-width"
              >
                {t("Kirish")}
                <ArrowRight size={18} />
              </Link>
            </>
          ) : (
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
              {/* Registration keeps the password above the Telegram step so it
                  stays in view; reset asks for the code first. */}
              {register ? (
                <div className="form-row">
                  {usernameField}
                  {passwordField}
                </div>
              ) : (
                !reset && (
                  <>
                    {usernameField}
                    {passwordField}
                  </>
                )
              )}
              {(register || reset) && (
                <RegistrationPhone
                  disabled={busy}
                  purpose={reset ? "password-reset" : "registration"}
                />
              )}
              {reset && (
                <div className="form-row">
                  {passwordField}
                  <Field label={t("Yangi parolni takrorlang")}>
                    <input
                      name="password_confirm"
                      type={show ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={8}
                      maxLength={128}
                      required
                    />
                  </Field>
                </div>
              )}
              {!register && !reset && (
                <Link
                  className="auth-recovery"
                  href={`/forgot-password${continuation}`}
                >
                  {t("Parolni unutdingizmi?")}
                </Link>
              )}
              <button className="button primary full-width" disabled={busy}>
                {busy
                  ? t("Kutilmoqda…")
                  : reset
                    ? t("Parolni yangilash")
                    : register
                      ? t("Akkaunt yaratish")
                      : t("Kirish")}
                <ArrowRight size={18} />
              </button>
            </form>
          )}
          {!done && (
            <>
              <p className="auth-switch">
                {reset
                  ? t("Parolingiz esingizdami?")
                  : register
                    ? t("Akkauntingiz bormi?")
                    : t("Hali akkauntingiz yo‘qmi?")}{" "}
                <Link
                  href={`${register || reset ? "/login" : "/register"}${continuation}`}
                >
                  {register || reset ? t("Kirish") : t("Ro‘yxatdan o‘tish")}
                </Link>
              </p>
              {register && (
                <p className="auth-switch">
                  <Link href={`/forgot-password${continuation}`}>
                    {t("Parolni unutdingizmi?")}
                  </Link>
                </p>
              )}
              {reset && (
                <p className="auth-help">
                  {t(
                    "Telegramga kira olmayapsizmi yoki akkauntingiz avval botga ulanmaganmi?",
                  )}{" "}
                  <a
                    href="https://t.me/murodjonerkinov"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("Administratorga yozing")}
                  </a>
                </p>
              )}
            </>
          )}
        </div>
        <span className="auth-copyright">
          © {new Date().getFullYear()}
          {t("YukFlow. Yo‘lingiz ochiq bo‘lsin.")}
        </span>
      </section>
    </>
  );
}
