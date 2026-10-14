"use client";
import { useLocale } from "@/components/locale";

import Link from "next/link";
import {
  ArrowRight,
  LoaderCircle,
  PackageSearch,
  TriangleAlert,
} from "lucide-react";
import { useSession } from "./session";
import { usePathname } from "next/navigation";

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { t } = useLocale();

  return (
    <div className={`field ${className}`}>
      <label>
        <span>{t(label)}</span>
        {children}
      </label>
      {hint && <small>{t(hint)}</small>}
    </div>
  );
}
export function ErrorBox({ message }: { message?: string }) {
  const { t } = useLocale();

  return message ? (
    <div className="error-box" role="alert">
      <TriangleAlert size={19} />
      <span>{t(message)}</span>
    </div>
  ) : null;
}
export function Loading({
  label = "Ma’lumotlar yuklanmoqda…",
}: {
  label?: string;
}) {
  const { t } = useLocale();

  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{t(label)}</span>
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  const { t } = useLocale();

  return (
    <div className="empty">
      <span className="empty-icon">
        <PackageSearch size={34} />
      </span>
      <h3>{t(title)}</h3>
      <p>{t(description)}</p>
      {action}
    </div>
  );
}
export function Protected({ children }: { children: React.ReactNode }) {
  const { t } = useLocale();

  const { user, loading } = useSession();
  const path = usePathname();
  if (loading) return <Loading />;
  if (!user)
    return (
      <Empty
        title={t("Kabinetga xush kelibsiz")}
        description={t(
          "Yuklaringizni boshqarish va yangi e’lon joylash uchun akkauntingizga kiring.",
        )}
        action={
          <Link
            className="button primary"
            href={`/login?next=${encodeURIComponent(path)}`}
          >
            {t("Akkauntga kirish")}
            <ArrowRight size={17} />
          </Link>
        }
      />
    );
  return children;
}
