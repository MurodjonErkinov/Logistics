"use client";

import Link from "next/link";
import Image from "next/image";
import { appPath } from "@/lib/paths";
import { useState, type KeyboardEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Check,
  ChevronDown,
  Menu,
  Package,
  Route,
  Send,
  SlidersHorizontal,
  Truck,
  X,
} from "lucide-react";
import { LanguageSwitcher, useLocale } from "./locale";
import styles from "./landing.module.css";
import { QuickShipment } from "./quick-shipment";

export function Landing() {
  const { locale } = useLocale();
  const c = (uz: string, ru: string) => (locale === "ru" ? ru : uz);
  const [audience, setAudience] = useState<"driver" | "dispatcher">("driver");
  const [menu, setMenu] = useState(false);
  const driver = audience === "driver";
  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? "driver"
        : event.key === "End"
          ? "dispatcher"
          : driver
            ? "dispatcher"
            : "driver";
    setAudience(next);
    document.getElementById(`${next}-tab`)?.focus();
  }
  const faqs = [
    [
      c("YukFlow nima?", "Что такое YukFlow?"),
      c(
        "YukFlow — haydovchilar va yuk joylovchilarni birlashtiradigan platforma. Bu yerda yuk e’lonlarini ko‘rish, yuk joylash, o‘zingizga mos yo‘nalish uchun tiket ochish va bildirishnomalar olish mumkin.",
        "YukFlow объединяет водителей и отправителей грузов. Здесь можно искать и размещать грузы, создавать заявки на маршруты и получать уведомления о совпадениях.",
      ),
    ],
    [
      c(
        "Ro‘yxatdan o‘tishda qaysi rolni tanlayman?",
        "Какую роль выбрать при регистрации?",
      ),
      c(
        "Yuk tashish uchun Haydovchi rolini, yuk e’lonlarini joylash uchun Dispetcher rolini tanlang. Ro‘yxatdan o‘tgach, tanlangan rolingizga mos kabinet ochiladi.",
        "Для поиска грузов выберите роль «Водитель», для размещения — «Диспетчер». После регистрации откроется кабинет для вашей роли.",
      ),
    ],
    [
      c(
        "Mos yuklar haqida qanday xabar olaman?",
        "Как получать уведомления о подходящих грузах?",
      ),
      c(
        "Haydovchi kabinetida mashinangizni qo‘shing va yo‘nalish, sig‘im, vaqt hamda narx shartlari bilan tiket oching. Mosliklar saytning bildirishnomalar bo‘limida chiqadi. Telegramni ulasangiz, sozlamalaringizga ko‘ra botga ham yuboriladi.",
        "Добавьте машину и создайте заявку с маршрутом, грузоподъёмностью, временем и ценой. Совпадения появятся в уведомлениях на сайте. Подключите Telegram, чтобы получать их и в боте с учётом ваших настроек.",
      ),
    ],
    [
      c("Yuk egasi bilan qanday bog‘lanaman?", "Как связаться с отправителем?"),
      c(
        "Akkauntingizga kirib, yuk tafsilotlarini oching. E’londa ko‘rsatilgan aloqa ma’lumotlari orqali bog‘laning. Yukning hali bo‘shligi, tashish narxi va boshqa shartlarni egasi bilan aniqlashtiring.",
        "Войдите в аккаунт и откройте объявление. Свяжитесь с отправителем по указанным контактам, уточните доступность груза, стоимость и условия перевозки.",
      ),
    ],
  ];
  const nav = (
    <>
      <a href="#possibilities" onClick={() => setMenu(false)}>
        {c("Imkoniyatlar", "Возможности")}
      </a>
      <a href="#how-it-works" onClick={() => setMenu(false)}>
        {c("Qanday ishlaydi?", "Как это работает?")}
      </a>
      <a href="#questions" onClick={() => setMenu(false)}>
        {c("Savol-javob", "Вопросы и ответы")}
      </a>
    </>
  );
  return (
    <div className={styles.landing}>
      <a href="#landing-content" className={styles.skip}>
        {c("Asosiy mazmunga o‘tish", "Перейти к содержимому")}
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand} aria-label="YukFlow">
            <span>
              <Route size={25} />
            </span>
            yukflow<span className={styles.brandDot}>.</span>
          </Link>
          <nav
            className={styles.desktopNav}
            aria-label={c("Bosh sahifa menyusi", "Меню главной страницы")}
          >
            {nav}
          </nav>
          <div className={styles.headerActions}>
            <LanguageSwitcher />
            <Link href="/login" className={styles.login}>
              {c("Kirish", "Войти")}
              <ArrowUpRight size={17} />
            </Link>
            <button
              className={styles.menuToggle}
              aria-label={c("Menyuni ochish", "Открыть меню")}
              aria-expanded={menu}
              aria-controls="landing-mobile-nav"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
        </div>
        {menu && (
          <nav
            id="landing-mobile-nav"
            className={styles.mobileNav}
            aria-label={c("Mobil menyu", "Мобильное меню")}
          >
            {nav}
            <Link href="/register">
              {c("Ro‘yxatdan o‘tish", "Регистрация")}
              <ArrowRight size={17} />
            </Link>
          </nav>
        )}
      </header>
      <main id="landing-content">
        <section className={styles.hero}>
          <Image
            src={appPath("/images/landing/convoy-hero.jpg")}
            alt=""
            fill
            priority
            sizes="(max-width: 540px) 2000px, 100vw"
            className={styles.heroPhoto}
          />
          <div className={styles.heroShade} />
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span />
              {c("YUK VA YO‘LNI BIRLASHTIRAMIZ", "ОБЪЕДИНЯЕМ ГРУЗЫ И МАРШРУТЫ")}
            </div>
            <h1>
              {c("Yukingizga yo‘l.", "Грузу — дорогу.")}
              <br />
              <em>{c("Yo‘lingizga yuk.", "В дорогу — груз.")}</em>
            </h1>
            <p>
              {c(
                "Yuk qidiring. Transport toping. Kelishing. Haydovchilar va yuk joylovchilar uchun yangi imkoniyatlar shu yerdan boshlanadi.",
                "Ищите грузы. Находите транспорт. Договаривайтесь. Новые возможности для водителей и отправителей начинаются здесь.",
              )}
            </p>
            <div className={styles.heroActions}>
              <Link href="/register?role=driver" className={styles.primary}>
                {c("Men haydovchiman", "Я водитель")}
                <ArrowUpRight size={20} />
              </Link>
              <Link
                href="/register?role=dispatcher"
                className={styles.secondary}
              >
                {c("Yuk joylamoqchiman", "Хочу разместить груз")}
                <ArrowUpRight size={20} />
              </Link>
            </div>
            <div className={styles.heroNote}>
              <Check size={16} />
              {c(
                "Bitta akkaunt. Saytda ham, Telegramda ham.",
                "Один аккаунт. На сайте и в Telegram.",
              )}
            </div>
          </div>
          <div className={styles.heroBottom}>
            <span>
              YUKFLOW / {c("YO‘LINGIZ OCHIQ BO‘LSIN", "СЧАСТЛИВОГО ПУТИ")}
            </span>
            <a href="#possibilities">
              {c("Platformani kashf eting", "Откройте платформу")}
              <ArrowDown size={17} />
            </a>
          </div>
        </section>
        <QuickShipment />
        <div className={`${styles.platformStrip} ${styles.container}`}>
          {[
            [
              Truck,
              c("Haydovchilar uchun", "Для водителей"),
              c("Yo‘nalishingizga mos yuklar", "Грузы по вашему маршруту"),
            ],
            [
              Package,
              c("Yuk joylovchilar uchun", "Для отправителей"),
              c(
                "E’londan bevosita aloqagacha",
                "От объявления до прямого контакта",
              ),
            ],
            [
              Send,
              c("Telegram bilan birga", "Вместе с Telegram"),
              c("Kerakli xabar, qulay joyda", "Нужные уведомления под рукой"),
            ],
          ].map(([Icon, title, text]) => {
            const I = Icon as typeof Truck;
            return (
              <div key={String(title)}>
                <I size={24} strokeWidth={1.5} />
                <div>
                  <strong>{String(title)}</strong>
                  <p>{String(text)}</p>
                </div>
              </div>
            );
          })}
        </div>
        <section
          id="possibilities"
          className={`${styles.section} ${styles.container}`}
        >
          <div className={styles.sectionHeading}>
            <div>
              <span className={styles.eyebrow}>
                {c("SIZNING ISHINGIZGA MOS", "ДЛЯ ВАШЕЙ РАБОТЫ")}
              </span>
              <h2>
                {c("Sizning ishingiz.", "Ваша работа.")}
                <br />
                {c("Sizning platformangiz.", "Ваша платформа.")}
              </h2>
            </div>
            <p>
              {c(
                "Yuk izlayapsizmi yoki transport? Kerakli ishlar uchun alohida kabinet, hammasi bir joyda.",
                "Ищете груз или размещаете объявление? Отдельный кабинет для вашей задачи — всё в одном месте.",
              )}
            </p>
          </div>
          <div
            className={styles.audienceTabs}
            role="tablist"
            aria-label={c("Imkoniyatlarni tanlash", "Выбор возможностей")}
          >
            <button
              id="driver-tab"
              role="tab"
              aria-selected={driver}
              aria-controls="audience-panel"
              tabIndex={driver ? 0 : -1}
              onClick={() => setAudience("driver")}
              onKeyDown={navigateTabs}
            >
              <Truck size={19} />
              {c("Haydovchiman", "Я водитель")}
            </button>
            <button
              id="dispatcher-tab"
              role="tab"
              aria-selected={!driver}
              aria-controls="audience-panel"
              tabIndex={!driver ? 0 : -1}
              onClick={() => setAudience("dispatcher")}
              onKeyDown={navigateTabs}
            >
              <Package size={19} />
              {c("Yuk joylovchiman", "Я отправитель")}
            </button>
          </div>
          <div
            id="audience-panel"
            role="tabpanel"
            aria-labelledby={driver ? "driver-tab" : "dispatcher-tab"}
            className={styles.audiencePanel}
          >
            <div className={styles.audienceCopy}>
              <span className={styles.smallLabel}>
                {driver
                  ? c("BO‘SH QAYTMANG", "НЕ ВОЗВРАЩАЙТЕСЬ ПОРОЖНЯКОМ")
                  : c("YUKINGIZNI TANISHTIRING", "РАССКАЖИТЕ О ВАШЕМ ГРУЗЕ")}
              </span>
              <h3>
                {driver
                  ? c(
                      "Keyingi reysingiz shu yerdan boshlanadi.",
                      "Ваш следующий рейс начинается здесь.",
                    )
                  : c(
                      "Yukingiz haqida kerakli ma’lumot. Kerakli joyda.",
                      "Всё о вашем грузе. В нужном месте.",
                    )}
              </h3>
              <p>
                {driver
                  ? c(
                      "Har bir e’lonni alohida qidirib o‘tirmang. Mashinangiz va yo‘nalishingizni kiriting, mosliklarni bir joyda kuzating.",
                      "Не перебирайте объявления вручную. Укажите машину и маршрут и следите за совпадениями в одном месте.",
                    )
                  : c(
                      "Yo‘nalish, transport talabi va tashish narxini ko‘rsating. Shaxsiy yoki kompaniya nomidan e’lonlaringizni boshqaring.",
                      "Укажите маршрут, требования к транспорту и стоимость. Управляйте объявлениями от себя или компании.",
                    )}
              </p>
              <Link
                href={`/register?role=${audience}`}
                className={styles.textLink}
              >
                {c("Boshlash", "Начать")}
                <ArrowUpRight size={19} />
              </Link>
            </div>
            <div className={styles.features}>
              {(driver
                ? [
                    [
                      Route,
                      c("Yo‘nalish bo‘yicha qidiring", "Ищите по маршруту"),
                      c(
                        "Qayerdan, qayerga, qanday mashina — filtrlar bilan kerakli yukni ajrating.",
                        "Откуда, куда и какой транспорт — находите подходящие грузы с помощью фильтров.",
                      ),
                    ],
                    [
                      SlidersHorizontal,
                      c(
                        "Shartlaringiz bilan tiket oching",
                        "Создайте заявку на своих условиях",
                      ),
                      c(
                        "Sig‘im, vaqt, narx va yo‘nalish. Qaysi mosliklar kerakligini o‘zingiz tanlang.",
                        "Грузоподъёмность, время, цена и маршрут. Выберите, какие совпадения вам нужны.",
                      ),
                    ],
                    [
                      Bell,
                      c(
                        "Mos yukdan xabardor bo‘ling",
                        "Узнавайте о подходящих грузах",
                      ),
                      c(
                        "Saytda bildirishnoma oling, xohlasangiz Telegram akkauntingizni ham ulang.",
                        "Получайте уведомления на сайте и подключите Telegram при желании.",
                      ),
                    ],
                  ]
                : [
                    [
                      Package,
                      c("Yuk e’lonini joylang", "Разместите груз"),
                      c(
                        "Manzil, og‘irlik, mashina turi va aloqa ma’lumotlarini bitta e’londa jamlang.",
                        "Укажите адреса, вес, транспорт и контакты в одном объявлении.",
                      ),
                    ],
                    [
                      Route,
                      c("E’lonlarni boshqaring", "Управляйте объявлениями"),
                      c(
                        "Yuk ma’lumotlarini tahrirlang, yuk ketganida e’lonni yoping.",
                        "Редактируйте информацию и закрывайте объявление, когда груз отправлен.",
                      ),
                    ],
                    [
                      Truck,
                      c("Jamoa bilan ishlang", "Работайте командой"),
                      c(
                        "Kompaniya yarating va a’zolarga yuk joylash huquqini bering.",
                        "Создайте компанию и предоставьте участникам право размещать грузы.",
                      ),
                    ],
                  ]
              ).map(([Icon, title, text]) => {
                const I = Icon as typeof Truck;
                return (
                  <div className={styles.feature} key={String(title)}>
                    <span>
                      <I size={22} />
                    </span>
                    <div>
                      <h4>{String(title)}</h4>
                      <p>{String(text)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
        <section id="how-it-works" className={styles.stepsSection}>
          <div className={styles.container}>
            <div className={styles.sectionHeading}>
              <div>
                <span className={styles.eyebrow}>
                  {c("ORTIQCHA MURAKKABLIKSIZ", "БЕЗ ЛИШНИХ СЛОЖНОСТЕЙ")}
                </span>
                <h2>
                  {c(
                    "Uch qadam. Yo‘lga tayyorsiz.",
                    "Три шага. Вы готовы в путь.",
                  )}
                </h2>
              </div>
              <a href="#get-started" className={styles.textLink}>
                {c("Birga boshlaymiz", "Давайте начнём")}
                <ArrowDown size={18} />
              </a>
            </div>
            <div className={styles.steps}>
              {[
                [
                  c("O‘z rolingizni tanlang", "Выберите свою роль"),
                  c(
                    "Haydovchi yoki dispetcher sifatida ro‘yxatdan o‘ting. Sizga mos ish kabinetini ochamiz.",
                    "Зарегистрируйтесь как водитель или диспетчер. Откроется кабинет для ваших задач.",
                  ),
                ],
                [
                  c(
                    "Kerakli ma’lumotni kiriting",
                    "Добавьте нужную информацию",
                  ),
                  c(
                    "Yuk e’lonini joylang yoki mashinangiz va yo‘nalishingiz uchun qidiruv tiketi yarating.",
                    "Разместите груз или создайте заявку на поиск под вашу машину и маршрут.",
                  ),
                ],
                [
                  c("Toping va bog‘laning", "Находите и связывайтесь"),
                  c(
                    "Mos e’lonlarni ko‘ring. Yuk egasi bilan bevosita bog‘lanib, tashish shartlarini kelishing.",
                    "Находите подходящие объявления. Связывайтесь с отправителем и согласовывайте условия.",
                  ),
                ],
              ].map(([title, text], i) => (
                <div className={styles.step} key={title}>
                  <span className={styles.stepNumber}>
                    0{i + 1}
                    <ArrowRight size={22} />
                  </span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className={`${styles.telegramSection} ${styles.container}`}>
          <div>
            <span className={styles.eyebrow}>
              <Send size={15} />
              {c("YUKFLOW × TELEGRAM", "YUKFLOW × TELEGRAM")}
            </span>
            <h2>
              {c("Yo‘lda bo‘lsangiz ham,", "Даже в дороге —")}
              <br />
              <em>{c("xabardor bo‘ling.", "будьте в курсе.")}</em>
            </h2>
            <p>
              {c(
                "Tiketlaringizga mos yuklar haqidagi xabarlarni o‘zingiz ishlatadigan messenjerda oling. Sayt va bot — bir akkauntga ulangan.",
                "Получайте уведомления о грузах по вашим заявкам в привычном мессенджере. Сайт и бот связаны одним аккаунтом.",
              )}
            </p>
            <ul>
              <li>
                <Check size={17} />
                {c(
                  "Mosliklar va tiketlarni boshqarish",
                  "Совпадения и управление заявками",
                )}
              </li>
              <li>
                <Check size={17} />
                {c(
                  "Bildirishnomalar va tinch vaqt sozlamalari",
                  "Настройки уведомлений и тихих часов",
                )}
              </li>
            </ul>
            <Link href="/register?role=driver" className={styles.lightButton}>
              {c("Haydovchi sifatida boshlash", "Начать как водитель")}
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <div className={styles.telegramPreview}>
            <div className={styles.chatHeader}>
              <span>
                <Route size={22} />
              </span>
              <div>
                <strong>YukFlow</strong>
                <small>
                  {c("Xabar ko‘rinishi · namuna", "Пример уведомления")}
                </small>
              </div>
              <Send size={19} />
            </div>
            <div className={styles.chatMessage}>
              <div className={styles.chatMatch}>
                <span />
                {c(
                  "Yo‘lingizga mos yuk topildi",
                  "Найден груз по вашему маршруту",
                )}
              </div>
              <h3>
                {c("Toshkent", "Ташкент")}
                <ArrowRight size={17} />
                {c("Samarqand", "Самарканд")}
              </h3>
              <p>{c("Qurilish materiallari", "Строительные материалы")}</p>
              <div className={styles.chatSpecs}>
                <span>
                  <Truck size={15} />
                  {c("Tent", "Тент")}
                </span>
                <span>
                  <Package size={15} />
                  20 {c("tonna", "тонн")}
                </span>
              </div>
              <div className={styles.chatChecks}>
                <Check size={14} />
                {c("Yo‘nalish", "Маршрут")}
                <Check size={14} />
                {c("Mashina turi", "Тип машины")}
              </div>
              <div className={styles.chatButton}>
                {c("Yuk tafsilotlarini ko‘rish", "Посмотреть груз")}
                <ArrowUpRight size={16} />
              </div>
            </div>
            <div className={styles.chatCaption}>
              <Bell size={15} />
              {c(
                "Siz tanlagan shartlar bo‘yicha xabarlar",
                "Уведомления по вашим условиям",
              )}
            </div>
          </div>
        </section>
        <section
          id="questions"
          className={`${styles.faqSection} ${styles.container}`}
        >
          <div>
            <span className={styles.eyebrow}>
              {c("BILIB OLISH FOYDALI", "ПОЛЕЗНО ЗНАТЬ")}
            </span>
            <h2>
              {c("Savollar bormi?", "Есть вопросы?")}
              <br />
              {c("Javoblar shu yerda.", "Ответы здесь.")}
            </h2>
            <p>
              {c(
                "Boshlashdan oldin bilishingiz kerak bo‘lgan eng asosiy ma’lumotlar.",
                "Главное, что нужно знать перед началом работы.",
              )}
            </p>
          </div>
          <div className={styles.faqList}>
            {faqs.map(([question, answer], i) => (
              <details key={question} open={i === 0 ? true : undefined}>
                <summary>
                  {question}
                  <ChevronDown size={20} />
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
        <section
          id="get-started"
          className={`${styles.finalCta} ${styles.container}`}
        >
          <div>
            <span className={styles.eyebrow}>
              {c("KEYINGI YO‘LINGIZ SHU YERDA", "ВАШ СЛЕДУЮЩИЙ МАРШРУТ ЗДЕСЬ")}
            </span>
            <h2>
              {c("Yuk bor. Yo‘l bor.", "Есть груз. Есть маршрут.")}
              <br />
              <em>{c("Endi siz ham borsiz.", "Теперь с вами.")}</em>
            </h2>
            <p>
              {c(
                "O‘z rolingizni tanlang. Qolganini birga boshlaymiz.",
                "Выберите свою роль. Начнём вместе.",
              )}
            </p>
          </div>
          <Link href="/register" className={styles.primary}>
            {c("Akkaunt yaratish", "Создать аккаунт")}
            <ArrowUpRight size={20} />
          </Link>
          <Route
            className={styles.ctaDecoration}
            size={240}
            strokeWidth={0.7}
          />
        </section>
      </main>
      <footer className={`${styles.footer} ${styles.container}`}>
        <div>
          <Link href="/" className={styles.brand}>
            <span>
              <Route size={23} />
            </span>
            yukflow<span className={styles.brandDot}>.</span>
          </Link>
          <p>
            {c("Har bir yukni o‘z manziliga.", "Каждому грузу — свой маршрут.")}
          </p>
        </div>
        <nav aria-label={c("Pastki menyu", "Меню внизу страницы")}>
          {nav}
          <Link href="/login">
            {c("Kirish", "Войти")}
            <ArrowUpRight size={14} />
          </Link>
        </nav>
        <div className={styles.footerBottom}>
          <span>© {new Date().getFullYear()} YukFlow</span>
          <span>
            {c(
              "Yuklar. Yo‘llar. Imkoniyatlar.",
              "Грузы. Маршруты. Возможности.",
            )}
          </span>
          <a href="#landing-content">
            {c("Yuqoriga", "Наверх")}
            <ArrowUpRight size={14} />
          </a>
        </div>
      </footer>
    </div>
  );
}
