"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell, CheckCheck, Phone, RefreshCw } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { DriverNotification } from "@/lib/driver-types";
import { DriverOnly } from "./driver-tools";
import { useLocale } from "./locale";
import { Empty, ErrorBox, Loading } from "./ui";

export function Notifications() {
  return (
    <DriverOnly>
      <Content />
    </DriverOnly>
  );
}
function Content() {
  const { t } = useLocale();
  const [notes, setNotes] = useState<DriverNotification[]>([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    try {
      const result = await api<{
        count: number;
        results: DriverNotification[];
      }>(`driver/notifications/?page=${page}`);
      setNotes(result.results);
      setCount(result.count);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 30000);
    return () => clearInterval(timer);
  }, [page]);
  async function act(path: string, body: unknown = {}) {
    setBusy(true);
    try {
      await api(path, {
        method: path.startsWith("driver/tickets/") ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      await refresh();
      window.dispatchEvent(new Event("driver-notifications"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const labels: Record<string, string> = {
    route: "Yo‘nalish",
    vehicle: "Mashina turi",
    capacity: "Sig‘im",
    time: "Vaqt",
    price: "Narx",
  };
  return (
    <div className="driver-tools">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("SIZ UCHUN TOPILDI")}</span>
          <h1>{t("Bildirishnomalar")}</h1>
          <p>
            {t(
              "Mos yuklar, narx o‘zgarishlari va tiket muddati haqida xabarlar.",
            )}
          </p>
        </div>
        <Link className="button primary" href="/driver/tickets">
          {t("Tiketlarim")}
        </Link>
      </div>
      <div className="ticket-actions">
        <button
          className="button secondary"
          disabled={busy}
          onClick={() => void act("driver/notifications/read-all/")}
        >
          <CheckCheck size={18} />
          {t("Barchasini o‘qilgan qilish")}
        </button>
        <button className="button secondary" onClick={() => void refresh()}>
          <RefreshCw size={17} />
          {t("Yangilash")}
        </button>
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : !notes.length ? (
        <Empty
          title="Hali bildirishnoma yo‘q"
          description="Tiket oching. Mos yuk topilganda xabar shu yerga keladi."
        />
      ) : (
        <div className="notification-list">
          {notes.map((note) => {
            const active =
              !!note.load && !note.obsolete && note.kind !== "unavailable";
            const expiry = ["expired", "expiring", "ticket_created"].includes(
              note.kind,
            );
            return (
              <article
                className={`notification-card ${note.read_at ? "" : "unread"}`}
                key={note.id}
              >
                <div className="card-top">
                  <span
                    className={`status-chip ${!active && !expiry ? "closed" : ""}`}
                  >
                    <Bell size={14} />
                    {t(
                      expiry
                        ? note.kind === "ticket_created"
                          ? "Tiket yaratildi"
                          : note.kind === "expired"
                            ? "Tiket muddati tugadi"
                            : "Tiket muddati tugayapti"
                        : !active
                          ? "Yuk yoki moslik eskirgan"
                          : note.level === "full"
                            ? "To‘liq mos"
                            : "Qisman mos",
                    )}
                  </span>
                  <small>{new Date(note.created_at).toLocaleString()}</small>
                </div>
                <Link className="notification-ticket" href="/driver/tickets">
                  #{note.ticket} · {note.ticket_title}
                </Link>
                <h2>
                  {expiry
                    ? note.ticket_title
                    : `${note.snapshot.origin} → ${note.snapshot.destination}`}
                </h2>
                {!expiry && (
                  <>
                    <p>
                      {note.snapshot.cargo_name} · {note.snapshot.weight_tons} t
                      · {note.snapshot.price || t("Kelishiladi")}{" "}
                      {note.snapshot.price ? note.snapshot.currency : ""}
                      {note.snapshot.price_basis === "ton" ? " / t" : ""}
                    </p>
                    {note.kind === "price" && (
                      <p>{t("Narx tiket shartiga moslashdi")}</p>
                    )}
                    <div className="match-checks">
                      {Object.entries(note.reasons.checks || {}).map(
                        ([key, value]) => (
                          <span
                            key={key}
                            className={
                              value === true
                                ? "yes"
                                : value === false
                                  ? "no"
                                  : "unknown"
                            }
                          >
                            {value === true ? "✓" : value === false ? "✕" : "?"}{" "}
                            {t(labels[key] || key)}
                          </span>
                        ),
                      )}
                    </div>
                    {note.reasons.distance_km != null && (
                      <p>
                        {t("Yuklash joyigacha to‘g‘ri chiziqda")}:{" "}
                        {note.reasons.distance_km} km
                      </p>
                    )}
                    {note.reasons.priority != null && (
                      <p>
                        {t("Manzil ustuvorligi")}: {note.reasons.priority}
                      </p>
                    )}
                  </>
                )}
                <div className="ticket-actions">
                  {active && (
                    <>
                      <Link
                        className="button primary small-button"
                        href={`/loads/${note.load}`}
                        onClick={() =>
                          void act(`driver/notifications/${note.id}/read/`)
                        }
                      >
                        {t("Yukni ko‘rish")}
                      </Link>
                      {note.snapshot.phone && (
                        <a
                          className="button secondary small-button"
                          href={`tel:${note.snapshot.phone}`}
                        >
                          <Phone size={15} />
                          {t("Qo‘ng‘iroq qilish")}
                        </a>
                      )}
                      <button
                        className="button secondary small-button"
                        disabled={busy}
                        onClick={() =>
                          void act(`driver/notifications/${note.id}/dismiss/`)
                        }
                      >
                        {t("Mos emas")}
                      </button>
                    </>
                  )}
                  {!note.read_at && (
                    <button
                      className="button secondary small-button"
                      disabled={busy}
                      onClick={() =>
                        void act(`driver/notifications/${note.id}/read/`)
                      }
                    >
                      {t("O‘qildi")}
                    </button>
                  )}
                  {expiry ? (
                    <>
                      <button
                        className="button secondary small-button"
                        disabled={busy}
                        onClick={() =>
                          void act(`driver/tickets/${note.ticket}/`, {
                            expires_at: new Date(
                              Date.now() + 7 * 86400000,
                            ).toISOString(),
                            status: "active",
                          })
                        }
                      >
                        {t("7 kunga uzaytirish")}
                      </button>
                      <button
                        className="button secondary small-button"
                        disabled={busy}
                        onClick={() =>
                          void act(`driver/tickets/${note.ticket}/`, {
                            status: "closed",
                          })
                        }
                      >
                        {t("Yopish")}
                      </button>
                    </>
                  ) : (
                    <button
                      className="button secondary small-button"
                      disabled={busy}
                      onClick={() =>
                        void act(`driver/tickets/${note.ticket}/`, {
                          status: "paused",
                        })
                      }
                    >
                      {t("Tiketni pauza qilish")}
                    </button>
                  )}
                </div>
                {!expiry && (
                  <p className="map-note">
                    {t(
                      "Moslik e’lon ma’lumotlariga asoslanadi. Yukning bo‘shligini egasidan aniqlang.",
                    )}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}
      <div className="ticket-actions">
        {page > 1 && (
          <button
            className="button secondary"
            onClick={() => setPage((n) => n - 1)}
          >
            {t("Oldingi")}
          </button>
        )}
        {page * 30 < count && (
          <button
            className="button secondary"
            onClick={() => setPage((n) => n + 1)}
          >
            {t("Keyingi")}
          </button>
        )}
      </div>
    </div>
  );
}
