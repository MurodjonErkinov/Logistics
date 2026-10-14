export class ApiError extends Error {
  constructor(
    public status: number,
    public details: Record<string, unknown>,
  ) {
    const messages = Object.entries(details).map(
      ([field, value]) =>
        `${field === "detail" || field === "non_field_errors" ? "" : field + ": "}${Array.isArray(value) ? value.join(" ") : String(value)}`,
    );
    super(
      status === 401
        ? "Davom etish uchun akkauntingizga kiring."
        : messages.join(" · ") || "So‘rov bajarilmadi. Qayta urinib ko‘ring.",
    );
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/${path.replace(/^\//, "")}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    credentials: "same-origin",
    cache: "no-store",
  });
  const data =
    response.status === 204
      ? null
      : await response
          .json()
          .catch(() => ({ detail: "Server bilan bog‘lanib bo‘lmadi." }));
  if (!response.ok) throw new ApiError(response.status, data || {});
  return data as T;
}
export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Xatolik yuz berdi. Qayta urinib ko‘ring.";
}
export function price(
  load: {
    is_price_negotiable: boolean;
    price_amount: string | null;
    currency: string;
    price_basis?: "trip" | "ton";
  },
  locale: "uz" | "ru" = "uz",
) {
  if (!load.price_amount) return "Kelishiladi";
  return `${new Intl.NumberFormat("ru-RU").format(Number(load.price_amount))} ${load.currency === "UZS" ? (locale === "ru" ? "сум" : "so‘m") : "$"}${load.price_basis === "ton" ? " / t" : ""}`;
}
export function dateLabel(value: string, locale: "uz" | "ru" = "uz") {
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "numeric",
    timeZone: "Asia/Tashkent",
  }).formatToParts(date);
  const day = parts.find((p) => p.type === "day")?.value;
  const month = Number(parts.find((p) => p.type === "month")?.value);
  const months =
    locale === "ru"
      ? [
          "янв",
          "фев",
          "мар",
          "апр",
          "май",
          "июн",
          "июл",
          "авг",
          "сен",
          "окт",
          "ноя",
          "дек",
        ]
      : [
          "yan",
          "fev",
          "mar",
          "apr",
          "may",
          "iyn",
          "iyl",
          "avg",
          "sen",
          "okt",
          "noy",
          "dek",
        ];
  return `${day} ${months[month - 1]}`;
}
