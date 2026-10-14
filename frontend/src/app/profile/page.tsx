"use client";
import { appPath } from "@/lib/paths";
import { useLocale } from "@/components/locale";

import { useState } from "react";
import { Check, Save, ShieldCheck } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { roleNames } from "@/lib/types";
import { useSession } from "@/components/session";
import { ErrorBox, Field, Protected } from "@/components/ui";
export default function Profile() {
  return (
    <Protected>
      <Content />
    </Protected>
  );
}
function Content() {
  const { t } = useLocale();

  const { user, reload } = useSession();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess(false);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (!data.password) delete data.password;
    try {
      await api("auth/me/", { method: "PATCH", body: JSON.stringify(data) });
      if (data.password) {
        window.location.assign(appPath("/login?password_changed=1"));
        return;
      }
      await reload();
      setSuccess(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  if (!user) return null;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{t("SHAXSIY KABINET")}</div>
          <h1>{t("Profil va sozlamalar")}</h1>
          <p>
            {t(
              "Ma’lumotlaringizni yangilab turing — siz bilan bog‘lanish oson bo‘lsin.",
            )}
          </p>
        </div>
      </div>
      <div className="form-layout">
        <form className="form-stack" onSubmit={submit}>
          <section className="form-section">
            <div className="profile-heading">
              <span className="avatar large">
                {(user.first_name || user.username).slice(0, 1).toUpperCase()}
              </span>
              <div>
                <h2>
                  {user.first_name || user.username} {user.last_name}
                </h2>
                <p>
                  @{user.username} · {t(roleNames[user.role])}
                </p>
              </div>
            </div>
            <ErrorBox message={error} />
            {success && (
              <div className="success-box" role="status">
                <Check size={18} />
                {t("Profil saqlandi.")}
              </div>
            )}
            <div className="form-row">
              <Field label={t("Ism")}>
                <input
                  name="first_name"
                  defaultValue={user.first_name}
                  maxLength={150}
                  autoComplete="given-name"
                />
              </Field>
              <Field label={t("Familiya")}>
                <input
                  name="last_name"
                  defaultValue={user.last_name}
                  maxLength={150}
                  autoComplete="family-name"
                />
              </Field>
            </div>
            <Field label={t("Telefon raqam")}>
              <input
                name="phone_number"
                type="tel"
                defaultValue={user.phone_number}
                placeholder="+998901234567"
                autoComplete="tel"
              />
            </Field>
            <Field label={t("Elektron pochta")}>
              <input
                name="email"
                type="email"
                defaultValue={user.email}
                autoComplete="email"
              />
            </Field>
            <Field
              label={t("Joriy parol")}
              hint={t("Faqat parolni almashtirayotganda kiriting.")}
            >
              <input
                name="current_password"
                type="password"
                autoComplete="current-password"
              />
            </Field>
            <Field
              label={t("Yangi parol")}
              hint={t("Parolni o‘zgartirmasangiz, bo‘sh qoldiring.")}
            >
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                placeholder={t("Kamida 8 belgi")}
              />
            </Field>
          </section>
          <div className="form-submit">
            <button className="button primary" disabled={busy}>
              <Save size={17} />
              {busy ? t("Saqlanmoqda…") : t("O‘zgarishlarni saqlash")}
            </button>
          </div>
        </form>
        <aside className="form-help">
          <ShieldCheck size={28} />
          <h3>{t("Sizning kabinetingiz")}</h3>
          <p>
            {t("Joriy rol:")}
            <strong>{t(roleNames[user.role])}</strong>.
          </p>
          <p>
            {t(
              "Rolni administrator o‘zgartiradi. Kompaniya nomidan yuk joylash ruxsatini kompaniya egasi beradi.",
            )}
          </p>
        </aside>
      </div>
    </>
  );
}
