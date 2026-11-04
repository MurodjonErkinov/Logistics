"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type InputHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { Check, LoaderCircle, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { useLocale } from "./locale";

export type CitySuggestion = {
  id: string;
  name: string;
  description: string;
  country_code: string;
  lat: number;
  lon: number;
};

type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "defaultValue" | "onChange"
> & {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  onSelectCity?: (city: CitySuggestion) => void;
};

export function CityInput({
  value,
  defaultValue = "",
  onValueChange,
  onSelectCity,
  className = "",
  onFocus,
  onBlur,
  onKeyDown,
  ...props
}: Props) {
  const { t, locale } = useLocale();
  const input = useRef<HTMLInputElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const listId = useId();
  const [internal, setInternal] = useState(defaultValue);
  const text = value ?? internal;
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<CitySuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"idle" | "empty" | "error">("idle");
  const [active, setActive] = useState(-1);
  const [position, setPosition] = useState({
    top: 0,
    left: 0,
    width: 0,
    maxHeight: 300,
  });
  const chosen = useRef("");
  const composing = useRef(false);
  const query = text.trim().replace(/\s+/g, " ");

  useEffect(() => {
    setResults([]);
    setStatus("idle");
    setActive(-1);
    setLoading(false);
    if (!open || query.length < 2 || query === chosen.current) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api<CitySuggestion[]>(
          `cargo/cities/?q=${encodeURIComponent(query)}&lang=${locale}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          setResults(data);
          setStatus(data.length ? "idle" : "empty");
        }
      } catch {
        if (!controller.signal.aborted) setStatus("error");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, open, locale]);

  const visible =
    open &&
    query.length >= 2 &&
    (loading || results.length > 0 || status !== "idle");
  useEffect(() => {
    if (!visible) return;
    function place() {
      const rect = input.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(Math.max(rect.width, 270), window.innerWidth - 24);
      const height = Math.min(320, results.length * 65 + 40 || 90);
      const below = window.innerHeight - rect.bottom - 12;
      const above = rect.top - 12;
      const upward = below < Math.min(height, 170) && above > below;
      const maxHeight = Math.max(60, Math.min(height, upward ? above : below));
      setPosition({
        top: upward ? Math.max(8, rect.top - maxHeight - 6) : rect.bottom + 6,
        left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        width,
        maxHeight,
      });
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [visible, results.length]);

  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (
        !input.current?.contains(event.target as Node) &&
        !popup.current?.contains(event.target as Node)
      )
        setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  function update(next: string) {
    setInternal(next);
    onValueChange?.(next);
  }
  function choose(city: CitySuggestion) {
    chosen.current = city.name;
    update(city.name);
    onSelectCity?.(city);
    setOpen(false);
    input.current?.focus();
  }
  function move(index: number) {
    const next = (index + results.length) % results.length;
    setActive(next);
    popup.current
      ?.querySelector(`#${CSS.escape(`${listId}-${next}`)}`)
      ?.scrollIntoView({ block: "nearest" });
  }

  return (
    <span className={`city-input ${className}`}>
      <input
        {...props}
        ref={input}
        value={text}
        maxLength={props.maxLength ?? 150}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={visible}
        aria-controls={visible ? listId : undefined}
        aria-activedescendant={
          visible && active >= 0 ? `${listId}-${active}` : undefined
        }
        autoComplete="off"
        onFocus={(event) => {
          setOpen(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          if (!popup.current?.contains(event.relatedTarget as Node))
            setOpen(false);
          onBlur?.(event);
        }}
        onCompositionStart={() => {
          composing.current = true;
        }}
        onCompositionEnd={() => {
          composing.current = false;
        }}
        onChange={(event) => {
          chosen.current = "";
          update(event.target.value);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (
            event.defaultPrevented ||
            composing.current ||
            event.nativeEvent.isComposing
          )
            return;
          if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
          } else if (
            (event.key === "ArrowDown" || event.key === "ArrowUp") &&
            results.length
          ) {
            event.preventDefault();
            setOpen(true);
            move(
              event.key === "ArrowDown"
                ? active + 1
                : active < 0
                  ? results.length - 1
                  : active - 1,
            );
          } else if (event.key === "Enter" && visible && active >= 0) {
            event.preventDefault();
            choose(results[active]);
          }
        }}
      />
      {loading && (
        <LoaderCircle
          className="city-input-spinner spin"
          size={16}
          aria-hidden="true"
        />
      )}
      {visible &&
        createPortal(
          <div ref={popup} className="city-popup" style={position}>
            <div className="city-popup-caption">{t("Shaharni tanlang")}</div>
            <div id={listId} role="listbox" aria-label={t("Mos shaharlar")}>
              {results.map((city, index) => (
                <button
                  key={city.id}
                  type="button"
                  id={`${listId}-${index}`}
                  role="option"
                  tabIndex={-1}
                  aria-selected={active === index}
                  className={`city-option ${active === index ? "active" : ""}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(city)}
                >
                  <MapPin size={18} />
                  <span>
                    <strong>{city.name}</strong>
                    <small>{city.description}</small>
                  </span>
                  {active === index && <Check size={16} />}
                </button>
              ))}
            </div>
            {loading && (
              <p className="city-popup-message" role="status">
                {t("Shaharlar qidirilmoqda…")}
              </p>
            )}
            {status === "empty" && (
              <p className="city-popup-message" role="status">
                {t("Shahar topilmadi. Nomini yozib davom etishingiz mumkin.")}
              </p>
            )}
            {status === "error" && (
              <p className="city-popup-message" role="status">
                {t("Qidiruv vaqtincha ishlamayapti. Manzilni qo‘lda kiriting.")}
              </p>
            )}
            <div className="city-popup-credit">© OpenStreetMap · Photon</div>
          </div>,
          document.body,
        )}
    </span>
  );
}
