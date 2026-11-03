"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Check,
  CheckCheck,
  LoaderCircle,
  Phone,
  ShieldCheck,
  Truck,
  Users,
  X,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Load } from "@/lib/types";
import { useLocale } from "./locale";
import { ErrorBox } from "./ui";

export function LoadClaim({ load }: { load: Load }) {
  const { t } = useLocale();
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const others = Math.max(
    0,
    (load.claim_count ?? 0) - (load.is_claimed ? 1 : 0),
  );
  async function take() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api<Load>(`cargo/loads/${load.id}/claim/`, {
        method: "POST",
        body: JSON.stringify({ confirmed_contact: true }),
      });
      dialog.current?.close();
      router.push("/driver");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="claim-panel panel">
        <div className="claim-panel-heading">
          <span className="claim-heading-icon">
            {load.is_claimed ? <CheckCheck size={24} /> : <Truck size={24} />}
          </span>
          <div>
            <span className="eyebrow">{t("SIZNING REYSINGIZ")}</span>
            <h3>
              {t(
                load.is_claimed
                  ? "Yuk sizning ro‘yxatingizda"
                  : "Bu yukni olib ketasizmi?",
              )}
            </h3>
          </div>
        </div>
        <p>
          {t(
            load.is_claimed
              ? "Manzil va yuk egasining ma’lumotlari «Mening yuklarim» bo‘limida ham saqlanadi."
              : "Avval yuk egasi bilan gaplashing, keyin yukni o‘z ro‘yxatingizga qo‘shing.",
          )}
        </p>
        <div className="claim-activity" aria-live="polite">
          <span className="claim-avatars" aria-hidden="true">
            <span>
              <Truck size={15} />
            </span>
            <span>
              <Users size={15} />
            </span>
          </span>
          <div>
            <strong>
              {others} {t("boshqa haydovchi")}
            </strong>
            <small>{t("shu yukni olgan")}</small>
          </div>
          <span
            className="haul-live-dot"
            title={t("Ma’lumotlar avtomatik yangilanadi")}
          />
        </div>
        {load.is_claimed ? (
          <Link href="/driver" className="button primary full-width">
            <Check size={18} />
            {t("Mening yuklarim")}
            <ArrowRight size={17} />
          </Link>
        ) : load.status === "open" ? (
          <button
            className="button primary full-width"
            onClick={() => {
              setError("");
              dialog.current?.showModal();
            }}
          >
            <Truck size={18} />
            {t("Yukni olish")}
            <ArrowRight size={17} />
          </button>
        ) : (
          <p className="notice">{t("Yopilgan e’lonni olish mumkin emas.")}</p>
        )}
        <small className="claim-footnote">
          <ShieldCheck size={14} />
          {t("Bu amal yukning faqat sizga ajratilganini anglatmaydi.")}
        </small>
      </section>
      <dialog
        ref={dialog}
        className="claim-dialog"
        aria-labelledby="claim-title"
        aria-describedby="claim-description"
        onCancel={(e) => {
          if (busy) e.preventDefault();
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget && !busy) dialog.current?.close();
        }}
      >
        <div className="claim-dialog-body">
          <button
            className="icon-button claim-dialog-close"
            aria-label={t("Yopish")}
            disabled={busy}
            onClick={() => dialog.current?.close()}
          >
            <X size={20} />
          </button>
          <span className="claim-dialog-icon">
            <Phone size={29} />
          </span>
          <span className="eyebrow">{t("BIR QADAM QOLDI")}</span>
          <h2 id="claim-title">{t("Yuk egasi bilan gaplashdingizmi?")}</h2>
          <p id="claim-description">
            {t(
              "Yuk hali bo‘shligini, narxini va manzillarini yuk egasi bilan kelishganingizni tasdiqlang.",
            )}
          </p>
          <div className="claim-dialog-route">
            <span>
              <Truck size={20} />
              {load.origin} <ArrowRight size={15} /> {load.destination}
            </span>
            <small>
              {load.cargo_name} · {Number(load.weight_tons)} t
            </small>
          </div>
          {load.contact_phone && (
            <a
              href={`tel:${load.contact_phone}`}
              className="claim-dialog-phone"
            >
              <Phone size={16} />
              {load.contact_phone}
            </a>
          )}
          <ErrorBox message={error} />
          <button
            className="button primary full-width"
            disabled={busy}
            onClick={() => void take()}
          >
            {busy ? (
              <LoaderCircle size={18} className="spin" />
            ) : (
              <CheckCheck size={18} />
            )}{" "}
            {t(busy ? "Yuk qo‘shilmoqda…" : "Ha, yukni olish")}
          </button>
          <button
            className="button secondary full-width"
            disabled={busy}
            onClick={() => dialog.current?.close()}
          >
            {t("Hali gaplashmadim")}
          </button>
        </div>
      </dialog>
    </>
  );
}
