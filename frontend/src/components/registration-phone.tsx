"use client";

import { useEffect, useState } from "react";
import { Send, ShieldCheck } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useLocale } from "./locale";
import { ErrorBox, Field } from "./ui";
import styles from "./registration-phone.module.css";

type Challenge = {
  verification_id: string;
  bot_url: string;
  retry_after: number;
};

export function RegistrationPhone({
  disabled,
  purpose = "registration",
}: {
  disabled: boolean;
  purpose?: "registration" | "password-reset";
}) {
  const { locale } = useLocale();
  const reset = purpose === "password-reset";
  const c = (uz: string, ru: string) => (locale === "ru" ? ru : uz);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retryAt, setRetryAt] = useState(0);
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    const update = () =>
      setRemaining(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);
  async function requestCode() {
    setError("");
    setBusy(true);
    // Open during the click so mobile popup blockers allow the Telegram tab.
    // The registration form stays open with all fields, including the password.
    const telegram = window.open("about:blank", "_blank");
    if (telegram) {
      telegram.opener = null;
      telegram.document.title = c(
        "Telegram ochilmoqda…",
        "Открываем Telegram…",
      );
      telegram.document.body.textContent = c(
        "Telegram ochilmoqda…",
        "Открываем Telegram…",
      );
    }
    try {
      const result = await api<Challenge>(
        reset ? "auth/password-reset-code/" : "auth/registration-code/",
        {
          method: "POST",
          body: JSON.stringify({ phone_number: phone }),
        },
      );
      setChallenge(result);
      setCode("");
      setRetryAt(Date.now() + result.retry_after * 1000);
      if (telegram && !telegram.closed)
        telegram.location.replace(result.bot_url);
    } catch (e) {
      if (telegram && !telegram.closed) telegram.close();
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={styles.verification}>
      <Field
        label={c("Telefon raqam", "Номер телефона")}
        hint={
          reset
            ? c(
                "Ro‘yxatdan o‘tgan telefon raqamingizni kiriting.",
                "Введите номер телефона, указанный при регистрации.",
              )
            : c(
                "Telegram akkauntingizga ulangan raqamni kiriting.",
                "Введите номер, привязанный к вашему Telegram.",
              )
        }
      >
        <input
          name="phone_number"
          type="tel"
          autoComplete="tel"
          placeholder="+998901234567"
          pattern="\+[1-9][0-9]{7,14}"
          required
          value={phone}
          disabled={disabled || busy}
          onChange={(event) => {
            setPhone(event.target.value);
            setChallenge(null);
            setRetryAt(0);
            setCode("");
            setError("");
          }}
        />
      </Field>
      {challenge ? (
        <a
          href={challenge.bot_url}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.open}
        >
          <Send size={17} />
          {c("Telegramga o‘tish", "Перейти в Telegram")}
        </a>
      ) : (
        <button
          type="button"
          className={styles.request}
          disabled={disabled || busy || !/^\+[1-9][0-9]{7,14}$/.test(phone)}
          onClick={requestCode}
        >
          <Send size={17} />
          {busy
            ? c("Telegram ochilmoqda…", "Открываем Telegram…")
            : c("Telegramdan kod olish", "Получить код в Telegram")}
        </button>
      )}
      <ErrorBox message={error} />
      {challenge && (
        <div className={styles.steps}>
          <p>
            {reset
              ? c(
                  "Raqamga Telegram ulangan bo‘lsa, botda Start bosganingizda kod beriladi. Kodni shu yerga kiriting.",
                  "Если к номеру привязан Telegram, нажмите Start в боте и введите полученный код здесь.",
                )
              : c(
                  "Telegramda Start → raqamni ulash. Kelgan kodni shu yerga kiriting.",
                  "В Telegram: Start → отправить номер. Введите полученный код здесь.",
                )}
          </p>
          <Field
            label={c("Tasdiqlash kodi", "Код подтверждения")}
            hint={c(
              "6 xonali kod 5 daqiqa amal qiladi.",
              "Код из 6 цифр действует 5 минут.",
            )}
          >
            <input
              className={styles.code}
              name="verification_code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              minLength={6}
              maxLength={6}
              required
              value={code}
              placeholder="000000"
              disabled={disabled}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
              }
            />
          </Field>
          <button
            type="button"
            className={styles.resend}
            disabled={disabled || busy || remaining > 0}
            onClick={requestCode}
          >
            {remaining
              ? c(`Yangi kod: ${remaining} s`, `Новый код через ${remaining} с`)
              : c("Yangi kod olish", "Получить новый код")}
          </button>
          <input
            type="hidden"
            name="verification_id"
            value={challenge.verification_id}
          />
        </div>
      )}
      {!challenge && (
        <p className={styles.hint}>
          <ShieldCheck size={16} />
          {reset
            ? c(
                "Kod faqat akkauntingizga avval ulangan Telegram orqali beriladi.",
                "Код доступен только в Telegram, ранее привязанном к вашему аккаунту.",
              )
            : c(
                "Ro‘yxatdan o‘tish uchun telefoningizni Telegram orqali tasdiqlang.",
                "Для регистрации подтвердите телефон через Telegram.",
              )}
        </p>
      )}
    </div>
  );
}
