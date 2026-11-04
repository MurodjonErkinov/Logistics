"use client";
import { TicketWizard } from "./ticket-wizard";
import { VehiclePicker } from "./vehicle-picker";
import { useEffect, useState } from "react";
import { Bell, MapPin, Plus, Ticket as TicketIcon, Truck } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Preferences, Ticket, Vehicle } from "@/lib/driver-types";
import { useSession } from "./session";
import { useLocale } from "./locale";
import { Empty, ErrorBox, Field, Loading, Protected } from "./ui";

export function DriverOnly({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  return (
    <Protected>
      {user?.role === "driver" ? (
        children
      ) : (
        <Empty
          title="Haydovchi uchun"
          description="Bu bo‘lim haydovchi akkaunti uchun mo‘ljallangan."
        />
      )}
    </Protected>
  );
}
export function DriverTools() {
  return (
    <DriverOnly>
      <Tools />
    </DriverOnly>
  );
}
function Tools() {
  const { t } = useLocale();
  const [tab, setTab] = useState("tickets");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [pref, setPref] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Ticket | null | undefined>(undefined);
  const [vehicleEdit, setVehicleEdit] = useState<Vehicle | null>(null);
  async function refresh() {
    try {
      const [ts, vs, ps] = await Promise.all([
        api<Ticket[]>("driver/tickets/"),
        api<Vehicle[]>("driver/vehicles/"),
        api<Preferences>("driver/preferences/"),
      ]);
      setTickets(ts);
      setVehicles(vs);
      setPref(ps);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    let active = true;
    async function syncTickets() {
      if (document.hidden) return;
      try {
        const [ts, vs] = await Promise.all([
          api<Ticket[]>("driver/tickets/"),
          api<Vehicle[]>("driver/vehicles/"),
        ]);
        if (active) {
          setTickets(ts);
          setVehicles(vs);
        }
      } catch {
        /* Keep the current list during a temporary connection failure. */
      }
    }
    const timer = window.setInterval(syncTickets, 20000);
    window.addEventListener("focus", syncTickets);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", syncTickets);
    };
  }, []);
  async function action(path: string, method: string, body?: unknown) {
    setError("");
    setSuccess("");
    setBusy(true);
    try {
      await api(path, {
        method,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
      await refresh();
      setSuccess(t("Saqlandi"));
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function saveVehicle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const saved = await action(
      `driver/vehicles/${vehicleEdit ? vehicleEdit.id + "/" : ""}`,
      vehicleEdit ? "PATCH" : "POST",
      { ...data, volume_m3: data.volume_m3 || null },
    );
    if (saved && editing !== undefined) setTab("tickets");
  }
  return (
    <div className="driver-tools">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("HAYDOVCHI KABINETI")}</span>
          <h1>{t("Yuk sizni topsin")}</h1>
          <p>
            {t(
              "Yo‘nalishlaringizni belgilang. Mos yuk haqida sayt va Telegramda xabar oling.",
            )}
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setEditing(null);
            setTab("tickets");
          }}
        >
          <Plus size={18} />
          {t("Tiket ochish")}
        </button>
      </div>
      <div className="ticket-tabs">
        {[
          ["tickets", "Tiketlarim", TicketIcon],
          ["vehicles", "Avtomobillarim", Truck],
          ["settings", "Xabar sozlamalari", Bell],
        ].map(([key, label, Icon]) => {
          const I = Icon as typeof Truck;
          return (
            <button
              key={key as string}
              className={tab === key ? "active" : ""}
              onClick={() => setTab(key as string)}
            >
              <I size={18} />
              {t(label as string)}
            </button>
          );
        })}
      </div>
      <ErrorBox message={error} />
      {success && (
        <p className="success-box" role="status">
          {success}
        </p>
      )}
      {editing !== undefined && (
        <div hidden={tab !== "tickets"}>
          <TicketWizard
            key={editing?.id ?? "new"}
            ticket={editing}
            vehicles={vehicles}
            onClose={() => setEditing(undefined)}
            onAddVehicle={() => {
              setVehicleEdit(null);
              setTab("vehicles");
            }}
            onSave={async () => {
              setEditing(undefined);
              await refresh();
              setSuccess(t("Tiket saytda ham, botda ham saqlandi."));
            }}
          />
        </div>
      )}
      {loading ? (
        <Loading />
      ) : tab === "tickets" ? (
        <>
          {!vehicles.length && editing === undefined && (
            <Empty
              title="Avval avtomobil qo‘shing"
              description="Tiketda mashinangiz va bo‘sh sig‘imini tanlaysiz."
              action={
                <button
                  className="button primary"
                  onClick={() => setTab("vehicles")}
                >
                  {t("Avtomobil qo‘shish")}
                </button>
              }
            />
          )}
          {tickets.length === 0 &&
            vehicles.length > 0 &&
            editing === undefined && (
              <Empty
                title="Hali tiket yo‘q"
                description="Tiket nomi, mashina va shaharlarni tanlang. Mos yuklar haqida xabar olasiz."
              />
            )}
          <div className="ticket-grid">
            {tickets.map((ticket) => (
              <article className="ticket-card" key={ticket.id}>
                <div className="card-top">
                  <span
                    className={`status-chip ${ticket.status !== "active" ? "closed" : ""}`}
                  >
                    {t(ticket.status)}
                  </span>
                  <small>#{ticket.id}</small>
                </div>
                <h2>{ticket.title}</h2>
                <p>
                  <MapPin size={16} />
                  {ticket.origins.map((p) => p.name).join(" / ")} →{" "}
                  {ticket.route_mode === "anywhere"
                    ? t("Istalgan manzil")
                    : ticket.destinations.map((p) => p.name).join(" / ")}
                </p>
                <p>
                  <Truck size={16} />
                  {ticket.vehicle_name} · {ticket.available_tons} t
                </p>
                <p>
                  {t("Yo‘nalish bo‘yicha qidiruv")} ·{" "}
                  {new Date(ticket.expires_at).toLocaleString()}
                </p>
                <div className="ticket-actions">
                  <button
                    className="button secondary small-button"
                    onClick={() => setEditing(ticket)}
                  >
                    {t("Tahrirlash")}
                  </button>
                  <button
                    className="button secondary small-button"
                    disabled={busy || ticket.status === "expired"}
                    onClick={() =>
                      void action(`driver/tickets/${ticket.id}/`, "PATCH", {
                        status:
                          ticket.status === "active" ? "paused" : "active",
                      })
                    }
                  >
                    {t(ticket.status === "active" ? "Pauza" : "Faollashtirish")}
                  </button>
                  <button
                    className="button secondary small-button"
                    disabled={busy}
                    onClick={() =>
                      void action(`driver/tickets/${ticket.id}/`, "PATCH", {
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
                    disabled={busy || ticket.route_mode === "anywhere"}
                    onClick={() =>
                      void action(
                        `driver/tickets/${ticket.id}/return-trip/`,
                        "POST",
                        {},
                      )
                    }
                  >
                    {t("Qaytish tiketi")}
                  </button>
                  <button
                    className="button secondary small-button"
                    disabled={busy}
                    onClick={() =>
                      void action(`driver/tickets/${ticket.id}/`, "PATCH", {
                        status: "closed",
                      })
                    }
                  >
                    {t("Yopish")}
                  </button>
                  <button
                    className="button secondary small-button danger"
                    disabled={busy}
                    onClick={() => {
                      if (
                        confirm(
                          t("Tiket va uning bildirishnomalari o‘chirilsinmi?"),
                        )
                      )
                        void action(`driver/tickets/${ticket.id}/`, "DELETE");
                    }}
                  >
                    {t("O‘chirish")}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : tab === "vehicles" ? (
        <>
          <section className="ticket-form">
            <h2>
              {t(vehicleEdit ? "Avtomobilni tahrirlash" : "Avtomobil qo‘shish")}
            </h2>
            <form
              key={vehicleEdit?.id ?? "new"}
              onSubmit={saveVehicle}
              className="form-stack"
            >
              <div className="form-row">
                <Field label={t("Mashina nomi")}>
                  <input
                    name="name"
                    maxLength={100}
                    required
                    defaultValue={vehicleEdit?.name}
                  />
                </Field>
              </div>
              <VehiclePicker
                driver
                kind={vehicleEdit?.kind}
                size={vehicleEdit?.size_class}
              />
              <div className="form-row">
                <Field label={t("Sig‘im (tonna)")}>
                  <input
                    name="capacity_tons"
                    type="number"
                    min="0.01"
                    step="0.01"
                    required
                    defaultValue={vehicleEdit?.capacity_tons}
                  />
                </Field>
                <Field label={t("Hajm (m³)")}>
                  <input
                    name="volume_m3"
                    type="number"
                    min="0.01"
                    step="0.01"
                    defaultValue={vehicleEdit?.volume_m3 ?? ""}
                  />
                </Field>
                <Field label={t("Davlat raqami")}>
                  <input
                    name="plate"
                    maxLength={20}
                    defaultValue={vehicleEdit?.plate}
                  />
                </Field>
              </div>
              <div className="ticket-actions">
                <button className="button primary" disabled={busy}>
                  {t("Saqlash")}
                </button>
                {vehicleEdit && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setVehicleEdit(null)}
                  >
                    {t("Yangi avtomobil")}
                  </button>
                )}
              </div>
            </form>
          </section>
          <div className="ticket-grid">
            {vehicles.map((v) => (
              <article className="ticket-card" key={v.id}>
                <Truck />
                <h2>{v.name}</h2>
                <p>
                  {t(v.kind)} · {v.capacity_tons} t · {v.plate}
                </p>
                <div className="ticket-actions">
                  <button
                    className="button secondary small-button"
                    onClick={() => setVehicleEdit(v)}
                  >
                    {t("Tahrirlash")}
                  </button>
                  <button
                    className="button secondary small-button"
                    disabled={busy}
                    onClick={() => {
                      if (confirm(t("Avtomobil o‘chirilsinmi?")))
                        void action(`driver/vehicles/${v.id}/`, "DELETE");
                    }}
                  >
                    {t("O‘chirish")}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : (
        pref && (
          <section className="ticket-form">
            <h2>
              <Bell size={22} /> {t("Bildirishnoma sozlamalari")}
            </h2>
            <p>
              {t(
                "Mos yuklar haqidagi xabarlar registratsiyada tasdiqlangan Telegram akkauntingizga avtomatik yuboriladi.",
              )}
            </p>
            {!pref.telegram_connected && (
              <ErrorBox
                message={t(
                  "Bu akkauntda tasdiqlangan Telegram topilmadi. Yordam uchun administratorga murojaat qiling.",
                )}
              />
            )}
            {pref.telegram_blocked && (
              <ErrorBox
                message={t(
                  "Bot bloklangan. Telegramda blokdan chiqaring va Start bosing — xabarlar yana keladi.",
                )}
              />
            )}
            {!pref.bot_configured && (
              <p className="map-note">
                {t(
                  "Bot serverda hali sozlanmagan. Saytdagi bildirishnomalar ishlaydi.",
                )}
              </p>
            )}
            <form
              className="form-stack"
              onSubmit={(e) => {
                e.preventDefault();
                void action("driver/preferences/", "PATCH", pref);
              }}
            >
              <Field label={t("Qisman mos yuklarni jamlash")}>
                <select
                  value={pref.partial_interval_minutes}
                  onChange={(e) =>
                    setPref({
                      ...pref,
                      partial_interval_minutes: Number(e.target.value),
                    })
                  }
                >
                  {[0, 15, 30, 60].map((v) => (
                    <option key={v} value={v}>
                      {v === 0 ? t("Darhol") : `${v} ${t("daqiqa")}`}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="form-row">
                <Field label={t("Tinch vaqt boshlanishi")}>
                  <input
                    type="time"
                    value={pref.quiet_start?.slice(0, 5) || ""}
                    onChange={(e) =>
                      setPref({ ...pref, quiet_start: e.target.value || null })
                    }
                  />
                </Field>
                <Field label={t("Tinch vaqt tugashi")}>
                  <input
                    type="time"
                    value={pref.quiet_end?.slice(0, 5) || ""}
                    onChange={(e) =>
                      setPref({ ...pref, quiet_end: e.target.value || null })
                    }
                  />
                </Field>
              </div>
              <div className="form-row">
                <Field label={t("Vaqt zonasi")}>
                  <input
                    value={pref.timezone}
                    onChange={(e) =>
                      setPref({ ...pref, timezone: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("Bot tili")}>
                  <select
                    value={pref.language}
                    onChange={(e) =>
                      setPref({ ...pref, language: e.target.value })
                    }
                  >
                    <option value="uz">O‘zbekcha</option>
                    <option value="ru">Русский</option>
                  </select>
                </Field>
              </div>
              <button className="button primary" disabled={busy}>
                {t("Saqlash")}
              </button>
            </form>
          </section>
        )
      )}
    </div>
  );
}
