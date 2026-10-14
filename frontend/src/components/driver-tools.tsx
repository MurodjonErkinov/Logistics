"use client";
import { VehiclePicker } from "./vehicle-picker";
import { useEffect, useState } from "react";
import {
  Bell,
  MapPin,
  Plus,
  Send,
  Ticket as TicketIcon,
  Truck,
  X,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Place, Preferences, Ticket, Vehicle } from "@/lib/driver-types";
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
const blankPlace = (): Place => ({
  name: "",
  radius_km: 0,
  priority: 1,
  eta_hours: 0,
});
const localTime = (iso: string) => {
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
function Places({
  title,
  places,
  setPlaces,
  dest = false,
}: {
  title: string;
  places: Place[];
  setPlaces: (p: Place[]) => void;
  dest?: boolean;
}) {
  const { t } = useLocale();
  function change(index: number, key: keyof Place, value: string) {
    setPlaces(
      places.map((p, i) =>
        i === index
          ? {
              ...p,
              [key]:
                key === "name" || key === "min_price"
                  ? value
                  : value === ""
                    ? null
                    : Number(value),
            }
          : p,
      ),
    );
  }
  return (
    <fieldset className="ticket-places">
      <legend>{title}</legend>
      {places.map((place, index) => (
        <div className="ticket-place" key={index}>
          <div className="ticket-place-main">
            <span className="ticket-number">{index + 1}</span>
            <Field label={`${t("Shahar")} ${index + 1}`}>
              <input
                required
                maxLength={150}
                value={place.name}
                onChange={(e) => change(index, "name", e.target.value)}
              />
            </Field>
            <button
              type="button"
              className="icon-button"
              aria-label={t("Manzilni olib tashlash")}
              onClick={() => setPlaces(places.filter((_, i) => i !== index))}
            >
              <X size={17} />
            </button>
          </div>
          <div className="ticket-place-fields">
            <Field label={t("Radius (km)")}>
              <input
                type="number"
                min="0"
                max="500"
                value={place.radius_km ?? 0}
                onChange={(e) => change(index, "radius_km", e.target.value)}
              />
            </Field>
            {dest && (
              <>
                <Field label={t("Eng kam narx")}>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={place.min_price ?? ""}
                    onChange={(e) => change(index, "min_price", e.target.value)}
                    placeholder={t("Umumiy narx")}
                  />
                </Field>
                <Field label={t("Yuklashgacha soat")}>
                  <input
                    type="number"
                    min="0"
                    max="720"
                    value={place.eta_hours ?? 0}
                    onChange={(e) => change(index, "eta_hours", e.target.value)}
                  />
                </Field>
                <Field label={t("Ustuvorlik (1 — afzal)")}>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={place.priority ?? 1}
                    onChange={(e) => change(index, "priority", e.target.value)}
                  />
                </Field>
              </>
            )}
          </div>
          <details>
            <summary>{t("Koordinatalar (radius uchun)")}</summary>
            <div className="form-row">
              <Field label={t("Kenglik")}>
                <input
                  type="number"
                  step="any"
                  min="-90"
                  max="90"
                  value={place.lat ?? ""}
                  onChange={(e) => change(index, "lat", e.target.value)}
                />
              </Field>
              <Field label={t("Uzunlik")}>
                <input
                  type="number"
                  step="any"
                  min="-180"
                  max="180"
                  value={place.lon ?? ""}
                  onChange={(e) => change(index, "lon", e.target.value)}
                />
              </Field>
            </div>
          </details>
        </div>
      ))}
      <button
        type="button"
        className="button secondary small-button"
        disabled={places.length >= 10}
        onClick={() => setPlaces([...places, blankPlace()])}
      >
        <Plus size={16} />
        {t("Manzil qo‘shish")}
      </button>
    </fieldset>
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
  const [link, setLink] = useState("");
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
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveVehicle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    await action(
      `driver/vehicles/${vehicleEdit ? vehicleEdit.id + "/" : ""}`,
      vehicleEdit ? "PATCH" : "POST",
      { ...data, volume_m3: data.volume_m3 || null },
    );
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
          disabled={!vehicles.length}
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
      {loading ? (
        <Loading />
      ) : tab === "tickets" ? (
        <>
          {!vehicles.length && (
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
          {editing !== undefined && (
            <TicketForm
              key={editing?.id ?? "new"}
              ticket={editing}
              vehicles={vehicles}
              onClose={() => setEditing(undefined)}
              onSave={async () => {
                setEditing(undefined);
                await refresh();
              }}
            />
          )}
          {tickets.length === 0 &&
            vehicles.length > 0 &&
            editing === undefined && (
              <Empty
                title="Hali tiket yo‘q"
                description="Qayerga, qachon va qancha haq evaziga borishingizni belgilang."
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
                  {t(
                    ticket.match_mode === "any_two"
                      ? "Istalgan 2 shart"
                      : "Yo‘nalish yoki to‘liq moslik",
                  )}{" "}
                  · {new Date(ticket.expires_at).toLocaleString()}
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
              <Send size={22} /> {t("Telegram va bildirishnomalar")}
            </h2>
            <p>
              {t(
                pref.telegram_connected
                  ? "Telegram ulangan"
                  : "Telegram hali ulanmagan",
              )}
            </p>
            {pref.telegram_blocked && (
              <ErrorBox
                message={t("Bot bloklangan. Telegramda ochib, qayta ulang.")}
              />
            )}
            {!pref.bot_configured && (
              <p className="map-note">
                {t(
                  "Bot serverda hali sozlanmagan. Saytdagi bildirishnomalar ishlaydi.",
                )}
              </p>
            )}
            <div className="ticket-actions">
              <button
                disabled={busy || !pref.bot_configured}
                className="button primary"
                onClick={async () => {
                  setBusy(true);
                  try {
                    const r = await api<{ url: string }>(
                      "driver/telegram-link/",
                      { method: "POST", body: "{}" },
                    );
                    setLink(r.url);
                  } catch (e) {
                    setError(errorMessage(e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("Telegramni ulash")}
              </button>
              {pref.telegram_connected && (
                <button
                  className="button secondary"
                  onClick={() => void action("driver/telegram-link/", "DELETE")}
                >
                  {t("Uzish")}
                </button>
              )}
              <button
                className="button secondary"
                onClick={() => void refresh()}
              >
                {t("Yangilash")}
              </button>
            </div>
            {link && (
              <a
                className="button secondary"
                href={link}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("Botni ochish — havola 10 daqiqa amal qiladi")}
              </a>
            )}
            <form
              className="form-stack"
              onSubmit={(e) => {
                e.preventDefault();
                void action("driver/preferences/", "PATCH", pref);
              }}
            >
              <label className="ticket-checkbox">
                <input
                  type="checkbox"
                  checked={pref.telegram_enabled}
                  onChange={(e) =>
                    setPref({ ...pref, telegram_enabled: e.target.checked })
                  }
                />
                {t("Telegramga ham yuborish")}
              </label>
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
function TicketForm({
  ticket,
  vehicles,
  onClose,
  onSave,
}: {
  ticket: Ticket | null;
  vehicles: Vehicle[];
  onClose: () => void;
  onSave: () => Promise<void>;
}) {
  const { t } = useLocale();
  const [origins, setOrigins] = useState<Place[]>(
    ticket?.origins || [blankPlace()],
  );
  const [destinations, setDestinations] = useState<Place[]>(
    ticket?.destinations || [blankPlace()],
  );
  const [waypoints, setWaypoints] = useState<Place[]>(ticket?.waypoints || []);
  const [mode, setMode] = useState(ticket?.route_mode || "alternatives");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    const clean = (places: Place[]) =>
      places.map((p) => {
        const value = { ...p };
        if (!value.min_price) delete value.min_price;
        return value;
      });
    try {
      await api(`driver/tickets/${ticket ? ticket.id + "/" : ""}`, {
        method: ticket ? "PATCH" : "POST",
        body: JSON.stringify({
          ...data,
          ready_at: new Date(data.ready_at as string).toISOString(),
          expires_at: new Date(data.expires_at as string).toISOString(),
          vehicle: Number(data.vehicle),
          partial_load: data.partial_load === "on",
          origins: clean(origins),
          destinations: mode === "anywhere" ? [] : clean(destinations),
          waypoints: mode === "ordered" ? clean(waypoints) : [],
          current_location: {
            name: data.location_name || "GPS",
            lat: data.location_lat ? Number(data.location_lat) : null,
            lon: data.location_lon ? Number(data.location_lon) : null,
          },
        }),
      });
      await onSave();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="ticket-form">
      <div className="workspace-section-heading">
        <h2>{t(ticket ? "Tiketni tahrirlash" : "Yangi qidiruv tiketi")}</h2>
        <button
          type="button"
          className="icon-button"
          onClick={onClose}
          aria-label={t("Yopish")}
        >
          <X />
        </button>
      </div>
      <ErrorBox message={error} />
      <form onSubmit={submit} className="form-stack">
        <div className="form-row">
          <Field label={t("Tiket nomi")}>
            <input
              name="title"
              required
              maxLength={120}
              defaultValue={ticket?.title}
            />
          </Field>
          <Field label={t("Avtomobil")}>
            <select
              name="vehicle"
              defaultValue={ticket?.vehicle || vehicles[0]?.id}
            >
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} · {v.capacity_tons} t
                </option>
              ))}
            </select>
          </Field>
        </div>
        <fieldset className="ticket-places">
          <legend>{t("Hozirgi joylashuv")}</legend>
          <div className="form-row">
            <Field label={t("Shahar")}>
              <input
                name="location_name"
                maxLength={150}
                defaultValue={ticket?.current_location.name}
              />
            </Field>
            <Field label={t("Kenglik")}>
              <input
                name="location_lat"
                type="number"
                step="any"
                min="-90"
                max="90"
                defaultValue={ticket?.current_location.lat ?? ""}
              />
            </Field>
            <Field label={t("Uzunlik")}>
              <input
                name="location_lon"
                type="number"
                step="any"
                min="-180"
                max="180"
                defaultValue={ticket?.current_location.lon ?? ""}
              />
            </Field>
          </div>
          <small>
            {t(
              "Botda lokatsiya yuborish mumkin. Masofa faqat koordinatalar mavjud bo‘lsa hisoblanadi.",
            )}
          </small>
        </fieldset>
        <Places
          title={t("Yuklash joylari")}
          places={origins}
          setPlaces={setOrigins}
        />
        <Field label={t("Yo‘nalish tartibi")}>
          <select
            name="route_mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="alternatives">
              {t("Muqobil manzillar — bittasiga boraman")}
            </option>
            <option value="ordered">
              {t("Ketma-ket yo‘l — oraliq shaharlar orqali")}
            </option>
            <option value="anywhere">{t("Istalgan manzil")}</option>
          </select>
        </Field>
        {mode !== "anywhere" && (
          <Places
            title={t("Boradigan manzillar")}
            places={destinations}
            setPlaces={setDestinations}
            dest
          />
        )}
        {mode === "ordered" && (
          <Places
            title={t("Oraliq shaharlar — yo‘l tartibida")}
            places={waypoints}
            setPlaces={setWaypoints}
          />
        )}
        <div className="form-row">
          <Field label={t("Tayyor vaqt")}>
            <input
              name="ready_at"
              type="datetime-local"
              required
              defaultValue={localTime(
                ticket?.ready_at || new Date().toISOString(),
              )}
            />
          </Field>
          <Field label={t("Tiket amal qilish muddati")}>
            <input
              name="expires_at"
              type="datetime-local"
              required
              defaultValue={localTime(
                ticket?.expires_at ||
                  new Date(Date.now() + 7 * 86400000).toISOString(),
              )}
            />
          </Field>
        </div>
        <div className="form-row">
          <Field label={t("Bo‘sh sig‘im (tonna)")}>
            <input
              name="available_tons"
              type="number"
              min="0.01"
              step="0.01"
              required
              defaultValue={
                ticket?.available_tons || vehicles[0]?.capacity_tons
              }
            />
          </Field>
          <Field label={t("Umumiy eng kam narx")}>
            <input
              name="min_price"
              type="number"
              min="0"
              step="0.01"
              required
              defaultValue={ticket?.min_price || "0"}
            />
          </Field>
          <Field label={t("Valyuta")}>
            <select name="currency" defaultValue={ticket?.currency || "UZS"}>
              <option>UZS</option>
              <option>USD</option>
            </select>
          </Field>
          <Field label={t("Narx birligi")}>
            <select
              name="price_basis"
              defaultValue={ticket?.price_basis || "trip"}
            >
              <option value="trip">{t("Butun reys")}</option>
              <option value="ton">{t("Tonnasiga")}</option>
            </select>
          </Field>
        </div>
        <label className="ticket-checkbox">
          <input
            name="partial_load"
            type="checkbox"
            defaultChecked={ticket?.partial_load}
          />
          {t("Qo‘shimcha yuk olaman (bo‘sh joyim bor)")}
        </label>
        <Field label={t("Qachon xabar berilsin?")}>
          <select
            name="match_mode"
            defaultValue={ticket?.match_mode || "any_two"}
          >
            <option value="any_two">{t("Istalgan 2 shart")}</option>
            <option value="route">{t("Yo‘nalish va sig‘im majburiy")}</option>
            <option value="full">{t("Faqat to‘liq mos")}</option>
          </select>
        </Field>
        <Field label={t("Izoh")}>
          <textarea
            name="notes"
            maxLength={1000}
            defaultValue={ticket?.notes}
          />
        </Field>
        <p className="map-note">
          {t(
            "Moslik yukning hali bo‘shligini tasdiqlamaydi. Yo‘l-yo‘lakay yuklar faqat kiritilgan oraliq shaharlar tartibida tekshiriladi.",
          )}
        </p>
        <button className="button primary" disabled={busy}>
          {t(busy ? "Kutilmoqda…" : "Tiketni saqlash")}
        </button>
      </form>
    </section>
  );
}
