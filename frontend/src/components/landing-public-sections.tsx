"use client";

import Link from "next/link";
import {
  ArrowDown,
  ArrowUpRight,
  BellRing,
  Building2,
  Check,
  MessageCircle,
  PackagePlus,
  Phone,
  Route,
  Send,
} from "lucide-react";
import { useLocale } from "./locale";
import styles from "./landing-public-sections.module.css";

export function LandingServices() {
  const { locale } = useLocale();
  const c = (uz: string, ru: string) => (locale === "ru" ? ru : uz);
  const services = [
    {
      icon: PackagePlus,
      title: c("Yukingizga haydovchi toping", "Найдите водителя для груза"),
      description: c(
        "Yo‘nalish, yuk turi, og‘irligi va taklif narxini bitta e’londa ko‘rsating. Qiziqqan haydovchilar siz bilan bevosita bog‘lanadi.",
        "Укажите маршрут, тип груза, вес и вашу цену в одном объявлении. Заинтересованные водители свяжутся с вами напрямую.",
      ),
      audience: c("Yuk jo‘natuvchilar uchun", "Для отправителей"),
      action: c("Yuk yuborish", "Отправить груз"),
      href: "#send-load",
    },
    {
      icon: Route,
      title: c("Keyingi reysingizni toping", "Найдите следующий рейс"),
      description: c(
        "Mashinangiz va yo‘nalishingizga mos yuklarni qidiring. O‘zingizga qulay vazn, vaqt va narx shartlari bilan tiket oching.",
        "Ищите грузы под вашу машину и маршрут. Создайте заявку с подходящими условиями по весу, времени и цене.",
      ),
      audience: c("Haydovchilar uchun", "Для водителей"),
      action: c("Yuk qidirishni boshlash", "Начать поиск грузов"),
      href: "/register?role=driver",
    },
    {
      icon: BellRing,
      title: c("Mos yukni o‘tkazib yubormang", "Не пропустите подходящий груз"),
      description: c(
        "Tiketga mos yangi yuk chiqqanda saytda va ulangan Telegram botda xabar oling. Bildirishnomalar hamda tinch vaqtni o‘zingiz sozlang.",
        "Получайте уведомления о новых совпадениях на сайте и в подключённом Telegram-боте. Настройте уведомления и тихие часы.",
      ),
      audience: c("Sayt + Telegram", "Сайт + Telegram"),
      action: c("Imkoniyatlarni ko‘rish", "Подробнее о возможностях"),
      href: "#possibilities",
    },
    {
      icon: Building2,
      title: c("Jamoangiz bilan ishlang", "Работайте всей командой"),
      description: c(
        "Kompaniya nomidan yuk joylang, xodimlarni qo‘shing va ularga e’lon joylash huquqini bering. Kompaniya yuklarini bir kabinetda boshqaring.",
        "Размещайте грузы от компании, добавляйте сотрудников и выдавайте права на публикацию. Управляйте грузами компании в одном кабинете.",
      ),
      audience: c("Kompaniyalar uchun", "Для компаний"),
      action: c("Kompaniya bilan boshlash", "Начать работу от компании"),
      href: "/register?role=dispatcher",
    },
  ];
  return (
    <section
      id="services"
      className={styles.services}
      aria-labelledby="services-title"
    >
      <div className={styles.container}>
        <div className={styles.heading}>
          <div>
            <span className={styles.eyebrow}>
              {c("XIZMATLARIMIZ", "НАШИ УСЛУГИ")}
            </span>
            <h2 id="services-title">
              {c("Har bir yuk uchun", "Для каждого груза")}
              <br />
              <em>{c("qulay yechim.", "удобное решение.")}</em>
            </h2>
          </div>
          <p>
            {c(
              "Yuk yuborishdan keyingi reysni topishgacha. YukFlow kerakli odamlar va imkoniyatlarni bir joyga jamlaydi.",
              "От отправки груза до поиска следующего рейса. YukFlow объединяет нужных людей и возможности в одном месте.",
            )}
          </p>
        </div>
        <div className={styles.serviceGrid}>
          {services.map(({ icon: Icon, ...service }, index) => (
            <article className={styles.serviceCard} key={service.href + index}>
              <div className={styles.serviceTop}>
                <span className={styles.serviceIcon}>
                  <Icon size={27} strokeWidth={1.5} />
                </span>
                <span className={styles.number}>0{index + 1}</span>
              </div>
              <h3>{service.title}</h3>
              <p>{service.description}</p>
              <div className={styles.serviceBottom}>
                <small>{service.audience}</small>
                {service.href.startsWith("#") ? (
                  <a href={service.href}>
                    {service.action}
                    <ArrowUpRight size={18} />
                  </a>
                ) : (
                  <Link href={service.href}>
                    {service.action}
                    <ArrowUpRight size={18} />
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>
        <div className={styles.serviceNote}>
          <Check size={17} />
          <p>
            {c(
              "Tashish narxi va shartlarini yuk egasi hamda haydovchi bevosita kelishadi.",
              "Стоимость и условия перевозки отправитель и водитель согласовывают напрямую.",
            )}
          </p>
          <a href="#contact">
            {c("Savolingiz bormi?", "Есть вопросы?")}
            <ArrowDown size={16} />
          </a>
        </div>
      </div>
    </section>
  );
}

export type LandingContactDetails = {
  phone?: string;
  telegram?: string;
  email?: string;
};

export function LandingContact({
  details,
}: {
  details: LandingContactDetails;
}) {
  const { locale } = useLocale();
  const c = (uz: string, ru: string) => (locale === "ru" ? ru : uz);
  return (
    <section
      id="contact"
      className={`${styles.contact} ${styles.container}`}
      aria-labelledby="contact-title"
    >
      <div className={styles.contactIntro}>
        <span className={styles.eyebrow}>{c("BOG‘LANISH", "КОНТАКТЫ")}</span>
        <h2 id="contact-title">
          {c("Keling,", "Давайте")}
          <br />
          <em>{c("gaplashamiz.", "поговорим.")}</em>
        </h2>
        <p>
          {c(
            "Platforma haqida savolingiz yoki hamkorlik taklifingiz bormi? Sizga qulay usulda bog‘laning.",
            "Есть вопрос о платформе или предложение о сотрудничестве? Свяжитесь с нами удобным способом.",
          )}
        </p>
        <a className={styles.faqLink} href="#questions">
          <MessageCircle size={18} />
          {c("Ko‘p beriladigan savollar", "Частые вопросы")}
          <ArrowUpRight size={17} />
        </a>
      </div>
      <div className={styles.contactPanel}>
        <div className={styles.contactPanelTop}>
          <span className={styles.contactSymbol}>
            <MessageCircle size={28} strokeWidth={1.5} />
          </span>
          <span>YUKFLOW / {c("ALOQADAMIZ", "НА СВЯЗИ")}</span>
        </div>
        {details.telegram && (
          <a
            className={styles.contactLink}
            href={`https://t.me/${details.telegram.replace(/^@/, "")}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className={styles.contactIcon}>
              <Send size={23} />
            </span>
            <span>
              <small>
                {c("Telegram orqali yozing", "Напишите в Telegram")}
              </small>
              <strong>
                {details.telegram.startsWith("@")
                  ? details.telegram
                  : `@${details.telegram}`}
              </strong>
            </span>
            <ArrowUpRight size={23} />
          </a>
        )}
        {details.phone && (
          <a
            className={styles.contactLink}
            href={`tel:${details.phone.replace(/[^+\d]/g, "")}`}
          >
            <span className={styles.contactIcon}>
              <Phone size={23} />
            </span>
            <span>
              <small>{c("Qo‘ng‘iroq qiling", "Позвоните нам")}</small>
              <strong>{details.phone}</strong>
            </span>
            <ArrowUpRight size={23} />
          </a>
        )}
        {details.email && (
          <a className={styles.contactLink} href={`mailto:${details.email}`}>
            <span className={styles.contactIcon}>
              <MessageCircle size={23} />
            </span>
            <span>
              <small>{c("Email orqali yozing", "Напишите на почту")}</small>
              <strong>{details.email}</strong>
            </span>
            <ArrowUpRight size={23} />
          </a>
        )}
        <div className={styles.contactTip}>
          <PackagePlus size={21} />
          <p>
            {c("Yuk uchun transport kerakmi?", "Нужен транспорт для груза?")}
            <a href="#send-load">
              {c(
                "Yuk yuborish formasidan boshlang",
                "Начните с формы отправки груза",
              )}
              <ArrowUpRight size={15} />
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}
