"use client";

import { shipmentVehicles as vehicles } from "@/lib/shipment-vehicles";
import Image from "next/image";
import { ArrowRight, MapPin, PackageCheck } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { appPath } from "@/lib/paths";
import { useLocale } from "./locale";
import styles from "./quick-shipment.module.css";

export function QuickShipment() {
  const { locale } = useLocale();
  const c = (uz: string, ru: string) => (locale === "ru" ? ru : uz);
  const router = useRouter();
  const [size, setSize] = useState("labo");
  return (
    <section id="send-load" className={styles.section}>
      <div className={styles.heading}>
        <span>{c("BIRINCHI QADAM SHU YERDA", "НАЧНИТЕ ЗДЕСЬ")}</span>
        <h2>{c("Yuk yuborish", "Отправить груз")}</h2>
        <p>
          {c(
            "Manzilni kiriting, transportni tanlang. Qolganini birga davom ettiramiz.",
            "Укажите маршрут и выберите транспорт. Затем перейдём к деталям.",
          )}
        </p>
      </div>
      <form
        className={styles.grid}
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const query = new URLSearchParams({
            origin: String(data.get("origin")).trim(),
            destination: String(data.get("destination")).trim(),
            shipment_vehicle: size,
            price_amount: String(data.get("price_amount") || ""),
            currency: String(data.get("currency") || "UZS"),
          });
          router.push(
            `/register?role=dispatcher&next=${encodeURIComponent(`/loads/new?${query}`)}`,
          );
        }}
      >
        <div className={styles.card}>
          <h3>
            <span>01</span>
            {c("Yo‘nalish", "Маршрут")}
          </h3>
          <label>
            <MapPin size={18} />
            {c("Qayerdan", "Откуда")}
            <input
              name="origin"
              required
              pattern=".*\S.*"
              maxLength={150}
              placeholder={c("Masalan, Toshkent", "Например, Ташкент")}
            />
          </label>
          <div className={styles.routeLine} />
          <label>
            <MapPin size={18} />
            {c("Qayerga", "Куда")}
            <input
              name="destination"
              required
              pattern=".*\S.*"
              maxLength={150}
              placeholder={c("Masalan, Samarqand", "Например, Самарканд")}
            />
          </label>
          <p className={styles.note}>
            {c(
              "Shahar yoki aniq manzilni yozishingiz mumkin.",
              "Можно указать город или точный адрес.",
            )}
          </p>
        </div>
        <fieldset className={styles.card}>
          <legend className={styles.legend}>
            {c("Mashina tanlash", "Выбор машины")}
          </legend>
          <h3 aria-hidden="true">
            <span>02</span>
            {c("Mashina tanlash", "Выбор машины")}
          </h3>
          <div className={styles.vehicles}>
            {vehicles.map((vehicle) => (
              <label key={vehicle.id} className={styles.vehicle}>
                <input
                  type="radio"
                  name="vehicle_size"
                  value={vehicle.id}
                  checked={size === vehicle.id}
                  onChange={() => setSize(vehicle.id)}
                />
                <span>
                  <strong>{vehicle.title}</strong>
                  <small>
                    {vehicle.capacity} {c("tonnagacha", "тонн")}
                  </small>
                </span>
                <Image
                  src={appPath(vehicle.image)}
                  alt=""
                  width={116}
                  height={72}
                />
              </label>
            ))}
          </div>
          <p className={styles.note}>
            {c(
              "Sig‘im taxminiy. Kuzov va yuk tafsilotlarini keyingi qadamda belgilaysiz.",
              "Вместимость ориентировочная. Кузов и детали груза укажете на следующем шаге.",
            )}
          </p>
        </fieldset>
        <div className={`${styles.card} ${styles.summary}`}>
          <PackageCheck size={38} strokeWidth={1.4} />
          <h3>
            {c("Yukingiz yo‘lga tayyor bo‘lsin", "Подготовьте груз к отправке")}
          </h3>
          <p>
            {c(
              "E’lonni yakunlash uchun akkaunt yarating yoki kiring. Tanlagan ma’lumotlaringiz saqlanadi.",
              "Создайте аккаунт или войдите, чтобы завершить объявление. Выбранные данные сохранятся.",
            )}
          </p>
          <div className={styles.price}>
            <label htmlFor="shipment-price">
              {c("Taklif narxi (ixtiyoriy)", "Ваша цена (необязательно)")}
            </label>
            <div className={styles.priceInputs}>
              <input
                id="shipment-price"
                name="price_amount"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0"
              />
              <select
                name="currency"
                aria-label={c("Valyuta", "Валюта")}
                defaultValue="UZS"
              >
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
              </select>
            </div>
            <p>
              {c(
                "Butun yo‘l uchun narxni kiriting. Bo‘sh qoldirsangiz — kelishuv asosida.",
                "Укажите цену за весь рейс. Оставьте пустым, если цена договорная.",
              )}
            </p>
          </div>
          <button type="submit">
            {c("Yuk yuborishni boshlash", "Начать отправку")}
            <ArrowRight size={20} />
          </button>
        </div>
      </form>
    </section>
  );
}
