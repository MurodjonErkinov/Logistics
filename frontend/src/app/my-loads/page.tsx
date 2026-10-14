"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Package,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { api, dateLabel, errorMessage, price } from "@/lib/api";
import type { Load } from "@/lib/types";
import { Empty, ErrorBox, Loading, Protected } from "@/components/ui";
export default function MyLoads() {
  return (
    <Protected>
      <Content />
    </Protected>
  );
}
function Content() {
  const { t, locale } = useLocale();

  const [loads, setLoads] = useState<Load[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [filter, setFilter] = useState("all");
  const [deleting, setDeleting] = useState<Load | null>(null);
  async function refresh() {
    try {
      setLoads(await api<Load[]>("cargo/loads/?mine=1"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function update(load: Load, remove = false) {
    setBusy(load.id);
    setError("");
    try {
      await api(`cargo/loads/${load.id}/`, {
        method: remove ? "DELETE" : "PATCH",
        ...(remove
          ? {}
          : {
              body: JSON.stringify({
                status: load.status === "open" ? "closed" : "open",
              }),
            }),
      });
      setDeleting(null);
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }
  const visible = loads.filter((l) => filter === "all" || l.status === filter);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{t("SHAXSIY KABINET")}</div>
          <h1>{t("Mening yuklarim")}</h1>
          <p>{t("E’lonlaringizni boshqaring va tashilgan yuklarni yoping.")}</p>
        </div>
        <Link href="/loads/new" className="button primary">
          <Plus size={18} />
          {t("Yangi yuk")}
        </Link>
      </div>
      <div className="summary-cards">
        <div>
          <Package size={21} />
          <span>{t("Barcha e’lonlar")}</span>
          <strong>{loads.length}</strong>
        </div>
        <div>
          <span className="summary-dot" />
          <span>{t("Aktual yuklar")}</span>
          <strong>{loads.filter((l) => l.status === "open").length}</strong>
        </div>
        <div>
          <Check size={21} />
          <span>{t("Yopilgan e’lonlar")}</span>
          <strong>{loads.filter((l) => l.status === "closed").length}</strong>
        </div>
      </div>
      <div className="tabs">
        {[
          ["all", t("Barchasi")],
          ["open", t("Aktual")],
          ["closed", t("Yopilgan")],
        ].map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => setFilter(value)}
          >
            {t(label)}
          </button>
        ))}
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : visible.length === 0 ? (
        <Empty
          title={t("Hozircha e’lon yo‘q")}
          description={t(
            "Yukingiz haqida ma’lumot kiriting va mos haydovchi toping.",
          )}
          action={
            <Link href="/loads/new" className="button primary">
              <Plus size={17} />
              {t("Yuk joylash")}
            </Link>
          }
        />
      ) : (
        <div className="managed-loads">
          {visible.map((load) => (
            <article className="managed-load" key={load.id}>
              <div className="managed-icon">
                <Package size={23} />
              </div>
              <div className="managed-info">
                <Link href={`/loads/${load.id}`}>
                  <h3>
                    {load.origin} → {load.destination}
                    <ArrowUpRight size={16} />
                  </h3>
                </Link>
                <p>
                  {load.cargo_name} · {Number(load.weight_tons)} t ·{" "}
                  {dateLabel(load.created_at, locale)}
                </p>
                <small>{load.company_name || t("Shaxsiy e’lon")}</small>
              </div>
              <strong className="managed-price">
                {t(price(load, locale))}
              </strong>
              <span
                className={`status-chip ${load.status === "closed" ? "closed" : ""}`}
              >
                <span />
                {load.status === "open" ? t("Aktual") : t("Yopilgan")}
              </span>
              <div className="managed-actions">
                <Link
                  href={`/loads/${load.id}/edit`}
                  className="icon-button"
                  aria-label={t("Tahrirlash")}
                >
                  <Pencil size={17} />
                </Link>
                <button
                  className="button small-button secondary"
                  disabled={busy === load.id}
                  onClick={() => void update(load)}
                >
                  {load.status === "open" ? t("Yopish") : t("Qayta ochish")}
                </button>
                <button
                  className="icon-button danger"
                  aria-label={t("O‘chirish")}
                  disabled={busy === load.id}
                  onClick={() => setDeleting(load)}
                >
                  <Trash2 size={17} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {deleting && (
        <div className="modal-overlay">
          <section
            className="dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h2 id="delete-title">{t("E’lonni o‘chirasizmi?")}</h2>
            <p>
              {deleting.origin} → {deleting.destination}
              {t(". O‘chirilgan e’lonni tiklab bo‘lmaydi.")}
            </p>
            <div className="dialog-actions">
              <button
                autoFocus
                className="button secondary"
                onClick={() => setDeleting(null)}
                disabled={busy !== null}
              >
                {t("Bekor qilish")}
              </button>
              <button
                className="button danger-button"
                disabled={busy !== null}
                onClick={() => void update(deleting, true)}
              >
                {t("O‘chirish")}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
