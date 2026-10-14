"use client";
import { useLocale } from "@/components/locale";

import { VehiclePicker } from "./vehicle-picker";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  MapPin,
  Package,
  Phone,
  ShieldCheck,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Company, Load } from "@/lib/types";
import { ErrorBox, Field, Loading, Protected } from "./ui";
import { useSession } from "./session";

export function LoadForm({ id }: { id?: string }) {
  return (
    <Protected>
      <Form id={id} />
    </Protected>
  );
}
function Form({ id }: { id?: string }) {
  const { t } = useLocale();

  const { user } = useSession();
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [load, setLoad] = useState<Load | null>(null);
  const [negotiable, setNegotiable] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState("");
  useEffect(() => {
    api<Company[]>("partners/companies/?mine=1")
      .then(setCompanies)
      .catch((e) => setError(errorMessage(e)));
    if (id)
      api<Load>(`cargo/loads/${id}/`)
        .then((value) => {
          setLoad(value);
          setNegotiable(value.is_price_negotiable);
        })
        .catch((e) => setError(errorMessage(e)))
        .finally(() => setLoading(false));
  }, [id]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const body = {
      ...data,
      company: data.company ? Number(data.company) : null,
      pickup_date: data.pickup_date || null,
      price_amount: data.price_amount || null,
      origin_lat: data.origin_lat || null,
      origin_lon: data.origin_lon || null,
      destination_lat: data.destination_lat || null,
      destination_lon: data.destination_lon || null,
      is_price_negotiable: negotiable,
    };
    try {
      const result = await api<Load>(`cargo/loads/${id ? `${id}/` : ""}`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      router.push(`/loads/${result.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading />;
  if (id && !load) return <ErrorBox message={error || t("Yuk topilmadi.")} />;
  return (
    <>
      <Link href="/my-loads" className="back-link">
        <ArrowLeft size={16} />
        {t("Mening yuklarim")}
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{t("YANGI IMKONIYAT")}</div>
          <h1>
            {id ? t("Yukni tahrirlash") : t("Yukingizga haydovchi toping")}
          </h1>
          <p>
            {t(
              "To‘liq ma’lumot kiriting — mos haydovchi siz bilan bog‘lanadi.",
            )}
          </p>
        </div>
      </div>
      <div className="form-layout">
        <form className="form-stack" onSubmit={submit}>
          <ErrorBox message={error} />
          <section className="form-section">
            <h2>
              <span>01</span>
              {t("Kim nomidan joylaysiz?")}
            </h2>
            <Field label={t("E’lon egasi")}>
              <select
                name="company"
                defaultValue={load?.company || ""}
                disabled={Boolean(id)}
              >
                <option value="">
                  {t("Shaxsiy —")}
                  {user?.first_name || user?.username}
                </option>
                {companies
                  .filter((c) => c.can_post_cargo || c.id === load?.company)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
              {id && (
                <input
                  type="hidden"
                  name="company"
                  value={load?.company || ""}
                />
              )}
            </Field>
            {!id && !companies.some((c) => c.can_post_cargo) && (
              <p className="field-note">
                {t("Kompaniya nomidan joylash uchun")}{" "}
                <Link href="/companies">{t("kompaniya yarating")}</Link>
                {t("yoki egasidan ruxsat oling.")}
              </p>
            )}
          </section>
          <section className="form-section">
            <h2>
              <span>02</span>
              {t("Yo‘nalish va yuk")}
            </h2>
            <div className="form-row">
              <Field label={t("Qayerdan *")}>
                <input
                  name="origin"
                  required
                  maxLength={150}
                  defaultValue={load?.origin}
                  placeholder={t("Masalan, Andijon")}
                />
              </Field>
              <Field label={t("Qayerga *")}>
                <input
                  name="destination"
                  required
                  maxLength={150}
                  defaultValue={load?.destination}
                  placeholder={t("Masalan, Namangan")}
                />
              </Field>
            </div>
            <Field label={t("Yuk nomi *")}>
              <input
                name="cargo_name"
                required
                maxLength={255}
                defaultValue={load?.cargo_name}
                placeholder={t("Masalan, pustoy karzinka")}
              />
            </Field>
            <VehiclePicker
              key={load?.id ?? "new"}
              kind={load?.vehicle_kind}
              size={load?.vehicle_size}
              legacy={load?.vehicle_type}
            />
            <div className="form-row">
              <Field label={t("Og‘irlik (tonna) *")}>
                <input
                  name="weight_tons"
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="9999999.99"
                  required
                  defaultValue={load?.weight_tons}
                  placeholder="1.5"
                />
              </Field>
            </div>
            <Field label={t("Yuklash sanasi")}>
              <input
                name="pickup_date"
                type="date"
                defaultValue={load?.pickup_date || ""}
              />
            </Field>
          </section>
          <section className="form-section">
            <h2>
              <span>03</span>
              {t("Narx va aloqa")}
            </h2>
            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={negotiable}
                onChange={(e) => setNegotiable(e.target.checked)}
              />
              <span>{t("Narx kelishiladi")}</span>
            </label>
            <div className="form-row">
              <Field
                label={
                  negotiable
                    ? t("Taklif narxi (ixtiyoriy)")
                    : t("Tashish narxi *")
                }
              >
                <input
                  name="price_amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required={!negotiable}
                  defaultValue={load?.price_amount || ""}
                  placeholder="0"
                />
              </Field>
              <Field label={t("Valyuta")}>
                <select name="currency" defaultValue={load?.currency || "UZS"}>
                  <option value="UZS">{t("UZS — so‘m")}</option>
                  <option value="USD">{t("USD — dollar")}</option>
                </select>
              </Field>
            </div>
            <Field label={t("Narx birligi")}>
              <select
                name="price_basis"
                defaultValue={load?.price_basis || "trip"}
              >
                <option value="trip">{t("Butun reys")}</option>
                <option value="ton">{t("Tonnasiga")}</option>
              </select>
            </Field>
            <details>
              <summary>{t("Yuklash va tushirish koordinatalari")}</summary>
              <p className="map-note">
                {t(
                  "Koordinatalar haydovchiga masofa va radius bo‘yicha mos yukni topishga yordam beradi.",
                )}
              </p>
              <div className="form-row">
                {(
                  [
                    "origin_lat",
                    "origin_lon",
                    "destination_lat",
                    "destination_lon",
                  ] as const
                ).map((key, index) => (
                  <Field
                    key={key}
                    label={t(
                      [
                        "Yuklash kengligi",
                        "Yuklash uzunligi",
                        "Tushirish kengligi",
                        "Tushirish uzunligi",
                      ][index],
                    )}
                  >
                    <input
                      name={key}
                      type="number"
                      step="any"
                      min={index % 2 === 0 ? -90 : -180}
                      max={index % 2 === 0 ? 90 : 180}
                      defaultValue={load?.[key] ?? ""}
                    />
                  </Field>
                ))}
              </div>
            </details>
            <div className="form-row">
              <Field label={t("Telefon raqam *")}>
                <input
                  name="contact_phone"
                  type="tel"
                  required
                  maxLength={16}
                  defaultValue={load?.contact_phone || user?.phone_number}
                  placeholder="+998901234567"
                />
              </Field>
              <Field label={t("Qo‘shimcha telefon")}>
                <input
                  name="alternate_phone"
                  type="tel"
                  maxLength={16}
                  defaultValue={load?.alternate_phone}
                  placeholder={t("Ixtiyoriy")}
                />
              </Field>
            </div>
            <Field label={t("Qo‘shimcha ma’lumot")}>
              <textarea
                name="notes"
                rows={4}
                defaultValue={load?.notes}
                placeholder={t(
                  "Yuklash shartlari, to‘lov yoki boshqa muhim ma’lumotlar…",
                )}
              />
            </Field>
          </section>
          <div className="form-submit">
            <Link href="/my-loads" className="button secondary">
              {t("Bekor qilish")}
            </Link>
            <button className="button primary" disabled={busy}>
              {busy
                ? t("Saqlanmoqda…")
                : id
                  ? t("O‘zgarishlarni saqlash")
                  : t("Yukni joylash")}
              <ArrowRight size={18} />
            </button>
          </div>
        </form>
        <aside className="form-help">
          <span className="help-icon">
            <Package size={28} />
          </span>
          <h3>{t("Yaxshi e’lon tezroq topiladi.")}</h3>
          <p>
            {t(
              "Haydovchiga kerak bo‘ladigan asosiy ma’lumotlarni aniq kiriting.",
            )}
          </p>
          <ul>
            <li>
              <MapPin size={18} />
              {t("Yuklash va tushirish manzili")}
            </li>
            <li>
              <Package size={18} />
              {t("Yuk nomi va aniq og‘irligi")}
            </li>
            <li>
              <Phone size={18} />
              {t("Bog‘lanish uchun telefon")}
            </li>
          </ul>
          <div className="help-divider" />
          <ShieldCheck size={23} />
          <p>
            {t(
              "Yuk jo‘natilgach, e’lonni “Yopilgan” holatiga o‘tkazishni unutmang.",
            )}
          </p>
        </aside>
      </div>
    </>
  );
}
