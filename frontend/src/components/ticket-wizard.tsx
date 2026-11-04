"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Globe2,
  LoaderCircle,
  MapPin,
  Plus,
  Ticket as TicketIcon,
  Truck,
  X,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Place, Ticket, Vehicle } from "@/lib/driver-types";
import { CityInput } from "./city-input";
import { useLocale } from "./locale";
import { ErrorBox, Field } from "./ui";

export function TicketWizard({
  ticket,
  vehicles,
  onClose,
  onSave,
  onAddVehicle,
}: {
  ticket: Ticket | null;
  vehicles: Vehicle[];
  onClose: () => void;
  onSave: () => Promise<void>;
  onAddVehicle: () => void;
}) {
  const { t } = useLocale();
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState(ticket?.title ?? "");
  const [vehicleId, setVehicleId] = useState(ticket?.vehicle ?? 0);
  const [origins, setOrigins] = useState<Place[]>(ticket?.origins ?? []);
  const [destinations, setDestinations] = useState<Place[]>(
    ticket?.destinations ?? [],
  );
  const [draft, setDraft] = useState<Place>({ name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);
  const knownVehicles = useRef(new Set(vehicles.map((vehicle) => vehicle.id)));
  const heading = useRef<HTMLHeadingElement>(null);
  const vehicle = vehicles.find((v) => v.id === vehicleId);
  const labels = ["Tiket nomi", "Mashina", "Yuk olish", "Yetkazish"];
  const places = step === 2 ? origins : destinations;

  useEffect(() => {
    const added = vehicles.find((v) => !knownVehicles.current.has(v.id));
    knownVehicles.current = new Set(vehicles.map((v) => v.id));
    if (added && step === 1) {
      setVehicleId(added.id);
      setStep(2);
    }
  }, [vehicles, step]);
  useEffect(() => {
    heading.current?.focus();
  }, [step]);

  function advance(next: number) {
    setError("");
    setDraft({ name: "" });
    setStep(next);
  }
  function withDraft(list: Place[]) {
    const name = draft.name.trim();
    if (!name) return list;
    if (
      list.some(
        (p) =>
          p.name.toLocaleLowerCase() === name.toLocaleLowerCase() &&
          p.lat === draft.lat &&
          p.lon === draft.lon,
      )
    )
      return list;
    if (list.length >= 10)
      throw new Error(t("Ko‘pi bilan 10 ta manzil qo‘shish mumkin."));
    return [...list, { ...draft, name }];
  }
  function addPlace() {
    try {
      const next = withDraft(places);
      if (step === 2) setOrigins(next);
      else setDestinations(next);
      setDraft({ name: "" });
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  function back() {
    try {
      if (step >= 2) {
        const nextPlaces = withDraft(places);
        if (step === 2) setOrigins(nextPlaces);
        else setDestinations(nextPlaces);
      }
      advance(step - 1);
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function save(nextDestinations: Place[], anywhere = false) {
    if (saving.current) return;
    if (!vehicle) {
      setError(t("O‘zingizga tegishli mashinani tanlang."));
      setStep(1);
      return;
    }
    if (!anywhere && !nextDestinations.length) {
      setError(t("Shaharni tanlang yoki «Istalgan manzil»ni bosing."));
      return;
    }
    saving.current = true;
    setBusy(true);
    setError("");
    try {
      await api<Ticket>(
        `driver/tickets/${ticket ? `${ticket.id}/simple/` : "simple/"}`,
        {
          method: ticket ? "PATCH" : "POST",
          body: JSON.stringify({
            title: title.trim(),
            vehicle: vehicle.id,
            origins,
            destinations: anywhere ? [] : nextDestinations,
            route_mode: anywhere ? "anywhere" : "alternatives",
          }),
        },
      );
      await onSave();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  async function next() {
    setError("");
    if (step === 0) {
      if (!title.trim()) {
        setError(t("Tiket nomini kiriting."));
        return;
      }
      advance(1);
    } else if (step === 2) {
      try {
        const nextOrigins = withDraft(origins);
        if (!nextOrigins.length) {
          setError(t("Kamida bitta yuk olish shahrini tanlang."));
          return;
        }
        setOrigins(nextOrigins);
        advance(3);
      } catch (e) {
        setError(errorMessage(e));
      }
    } else if (step === 3) {
      try {
        await save(withDraft(destinations));
      } catch (e) {
        setError(errorMessage(e));
      }
    }
  }

  return (
    <section
      className="simple-ticket-wizard"
      aria-label={t(ticket ? "Tiketni tahrirlash" : "Tiket ochish")}
    >
      <header className="simple-ticket-header">
        <span className="simple-ticket-mark">
          <TicketIcon size={23} />
        </span>
        <div>
          <span className="eyebrow">{t("SODDA QIDIRUV")}</span>
          <h2>{t(ticket ? "Tiketni tahrirlash" : "Yangi tiket")}</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label={t("Yopish")}
          disabled={busy}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      <ol
        className="simple-ticket-steps"
        aria-label={t("Tiket ochish bosqichlari")}
      >
        {labels.map((label, i) => (
          <li
            key={label}
            className={i === step ? "current" : i < step ? "complete" : ""}
            aria-current={i === step ? "step" : undefined}
          >
            <span>{i < step ? <Check size={14} /> : i + 1}</span>
            <small>{t(label)}</small>
          </li>
        ))}
      </ol>
      <div className="simple-ticket-body">
        <div className="simple-ticket-question">
          <span>{step + 1} / 4</span>
          <h3 ref={heading} tabIndex={-1}>
            {t(
              [
                "Tiketingizga nom bering",
                "Mashinangizni tanlang",
                "Qayerdan yuk olasiz?",
                "Qayerga yuk olib borasiz?",
              ][step],
            )}
          </h3>
          <p>
            {t(
              [
                "Keyinroq tiketingizni oson topish uchun qisqa nom yozing.",
                "Yuk olib ketadigan avtomobilingizni tanlang.",
                "Bir yoki bir nechta shaharni tanlashingiz mumkin.",
                "Shaharlarni tanlang yoki istalgan yo‘nalishda borishni belgilang.",
              ][step],
            )}
          </p>
        </div>
        <ErrorBox message={error} />
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void next();
          }}
        >
          {step === 0 && (
            <Field label={t("Tiket nomi")}>
              <input
                name="title"
                maxLength={120}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t("Masalan, Toshkentdan yuk qidirish")}
                autoComplete="off"
              />
            </Field>
          )}
          {step === 1 && (
            <div className="simple-ticket-vehicles">
              {vehicles.map((v) => (
                <button
                  type="button"
                  key={v.id}
                  className={vehicleId === v.id ? "selected" : ""}
                  onClick={() => {
                    setVehicleId(v.id);
                    advance(2);
                  }}
                >
                  <span className="simple-ticket-vehicle-icon">
                    <Truck size={24} />
                  </span>
                  <span>
                    <strong>{v.name}</strong>
                    <small>
                      {t(v.kind)} · {Number(v.capacity_tons)} t
                      {v.plate ? ` · ${v.plate}` : ""}
                    </small>
                  </span>
                  <ArrowRight size={19} />
                </button>
              ))}
              <button
                type="button"
                className="simple-ticket-add-vehicle"
                onClick={onAddVehicle}
              >
                <Plus size={20} />
                {t("Mashina qo‘shish")}
              </button>
            </div>
          )}
          {step >= 2 && (
            <>
              <fieldset className="simple-ticket-city-group">
                <legend>
                  {t(step === 2 ? "Yuklash joylari" : "Boradigan manzillar")}
                </legend>
                <div className="simple-ticket-picked">
                  {places.map((place, i) => (
                    <div key={`${place.name}-${i}`}>
                      <span className="simple-ticket-city-number">{i + 1}</span>
                      <span>
                        <strong>{place.name}</strong>
                        {place.address && <small>{place.address}</small>}
                      </span>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`${t("Manzilni olib tashlash")}: ${place.name}`}
                        onClick={() =>
                          step === 2
                            ? setOrigins(
                                origins.filter((_, index) => index !== i),
                              )
                            : setDestinations(
                                destinations.filter((_, index) => index !== i),
                              )
                        }
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                </div>
                <Field label={t("Shahar")}>
                  <CityInput
                    value={draft.name}
                    placeholder={t("Shahar nomini yozing…")}
                    disabled={busy || places.length >= 10}
                    onValueChange={(name) => setDraft({ name })}
                    onSelectCity={(city) =>
                      setDraft({
                        name: city.name,
                        lat: city.lat,
                        lon: city.lon,
                        address: [city.name, city.description]
                          .filter(Boolean)
                          .join(", "),
                        geocoded: true,
                      })
                    }
                  />
                </Field>
                <button
                  type="button"
                  className="button secondary small-button simple-ticket-add-place"
                  disabled={!draft.name.trim() || places.length >= 10 || busy}
                  onClick={addPlace}
                >
                  <Plus size={17} />
                  {t("Manzil qo‘shish")}
                </button>
              </fieldset>
              {step === 3 && (
                <button
                  type="button"
                  className="simple-ticket-anywhere"
                  disabled={busy}
                  onClick={() => void save([], true)}
                >
                  <span>
                    <Globe2 size={25} />
                  </span>
                  <span>
                    <strong>{t("Istalgan manzil")}</strong>
                    <small>{t("Boradigan joyim muhim emas")}</small>
                  </span>
                  <ArrowRight size={18} />
                </button>
              )}
            </>
          )}
          <footer className="simple-ticket-actions">
            <button
              type="button"
              className="button secondary"
              disabled={busy}
              onClick={() => (step === 0 ? onClose() : back())}
            >
              <ArrowLeft size={16} />
              {t(step === 0 ? "Bekor qilish" : "Orqaga")}
            </button>
            {step !== 1 && (
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? <LoaderCircle size={17} className="spin" /> : null}
                {t(
                  busy
                    ? "Saqlanmoqda…"
                    : step === 3
                      ? ticket
                        ? "Tiketni saqlash"
                        : "Tiketni ochish"
                      : "Davom etish",
                )}
                {!busy && <ArrowRight size={17} />}
              </button>
            )}
          </footer>
        </form>
        <div className="simple-ticket-sync">
          <Check size={15} />
          <span>
            {t(
              "Tiket saytda ham, Telegram botda ham ko‘rinadi. Qidiruv 7 kun faol.",
            )}
          </span>
        </div>
        {step >= 2 && vehicle && (
          <div className="simple-ticket-summary">
            <Truck size={14} />
            {vehicle.name}
            {step === 3 && (
              <>
                <MapPin size={14} />
                {origins.map((p) => p.name).join(" / ")}
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
