"use client";
import { appPath } from "@/lib/paths";
import Image from "next/image";
import { Truck } from "lucide-react";
import { useState } from "react";
import { useLocale } from "./locale";

const sizes = [
  ["S", "0.3"],
  ["M", "0.7"],
  ["L", "1.4"],
  ["XL", "2"],
  ["XXL", "4"],
  ["3XL", "8"],
  ["FURA", "20"],
  ["CUSTOM", ""],
];
const bodies = [
  "tent",
  "van",
  "refrigerator",
  "isothermal",
  "flatbed",
  "tanker",
  "dump",
  "lowbed",
  "container",
  "other",
];
const labels: Record<string, string> = {
  tent: "Tent",
  van: "Furgon",
  refrigerator: "Refrijerator",
  isothermal: "Izotermik",
  flatbed: "Bort / platforma",
  tanker: "Sisterna",
  dump: "Samosval",
  lowbed: "Tral",
  container: "Konteyner",
  other: "Boshqa",
};

export function VehiclePicker({
  driver = false,
  kind,
  size,
  legacy,
}: {
  driver?: boolean;
  kind?: string;
  size?: string;
  legacy?: string;
}) {
  const { t } = useLocale();
  const [body, setBody] = useState(kind || (legacy ? "" : "tent"));
  const [selected, setSelected] = useState(size || "");
  const [text, setText] = useState(legacy || "");
  const preset = sizes.find(([key]) => key === selected);
  const imageSize = ["S", "M", "L", "XL", "XXL", "3XL"].includes(selected)
    ? selected
    : !selected
      ? "L"
      : null;
  function choose(nextBody: string, nextSize: string) {
    setBody(nextBody);
    setSelected(nextSize);
    setText(
      `${labels[nextBody] || legacy || ""}${nextSize && nextSize !== "CUSTOM" ? ` · ${nextSize}` : ""}`,
    );
  }
  return (
    <section className="vehicle-picker" aria-label={t("Transport tanlash")}>
      <div className="vehicle-preview">
        <div className="vehicle-preview-heading">
          <span>
            {t(driver ? "Mening avtomobilim" : "Yuk uchun transport")}
          </span>
          <strong>
            {selected === "CUSTOM"
              ? t("Boshqa")
              : selected || t("O‘lchamni tanlang")}
          </strong>
        </div>
        <div className="vehicle-image-stage">
          {imageSize ? (
            <Image
              src={appPath(`/images/vehicles/${imageSize.toLowerCase()}.webp`)}
              alt={`${imageSize} — ${t("Transport tanlash")}`}
              width={773}
              height={479}
              sizes="(max-width: 600px) 90vw, 520px"
              className="vehicle-reference-image"
            />
          ) : (
            <Truck size={100} strokeWidth={1} aria-hidden="true" />
          )}
        </div>
        <strong>
          {t(body || "other")}
          {preset?.[1] ? ` · ${preset[1]} ${t("tonnagacha")}` : ""}
        </strong>
        <p>
          {t(
            driver
              ? "Haqiqiy sig‘imni quyida kiriting"
              : "Yukingizga mos o‘lcham va kuzovni tanlang",
          )}
        </p>
      </div>
      <div
        className="vehicle-sizes"
        role="group"
        aria-label={t("Mashina o‘lchami")}
      >
        {sizes.map(([key, capacity]) => (
          <button
            key={key}
            type="button"
            aria-pressed={selected === key}
            onClick={(e) => {
              choose(body || "tent", key);
              if (driver && capacity) {
                const input =
                  e.currentTarget.form?.elements.namedItem("capacity_tons");
                if (input instanceof HTMLInputElement) input.value = capacity;
              }
            }}
          >
            {key === "CUSTOM" ? t("Boshqa") : key}
            <small>{capacity ? `${capacity} t` : "—"}</small>
          </button>
        ))}
      </div>
      <h3>{t("Kuzov turi")}</h3>
      <div className="vehicle-bodies" role="group" aria-label={t("Kuzov turi")}>
        {bodies.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={body === value}
            onClick={() => choose(value, selected)}
          >
            <span>
              {value === "refrigerator"
                ? "❄"
                : value === "isothermal"
                  ? "◈"
                  : "▱"}
            </span>
            {t(value)}
          </button>
        ))}
      </div>
      <p className="vehicle-hint">
        {t(
          body === "refrigerator"
            ? "Faol sovitish tizimi bor kuzov"
            : body === "isothermal"
              ? "Issiqlikdan himoyalangan kuzov, faol sovitishsiz"
              : "O‘lchamlar taxminiy toifalar; haqiqiy sig‘im mashinaga bog‘liq",
        )}
      </p>
      <input
        type="hidden"
        name={driver ? "kind" : "vehicle_kind"}
        value={body}
      />
      <input
        type="hidden"
        name={driver ? "size_class" : "vehicle_size"}
        value={selected}
      />
      {!driver && (
        <label className="vehicle-custom">
          {t("Kerakli transport *")}
          <input
            name="vehicle_type"
            value={text || labels[body] || ""}
            required
            maxLength={120}
            onChange={(e) => {
              setText(e.target.value);
              setBody("");
              setSelected("");
            }}
          />
        </label>
      )}
    </section>
  );
}
