"use client";
import { LanguageSwitcher, useLocale } from "@/components/locale";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ArrowUpRight,
  Bookmark,
  Building2,
  ChevronRight,
  Compass,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Plus,
  Route,
  Settings2,
  ShieldCheck,
  Truck,
  X,
} from "lucide-react";
import { NotificationBell } from "./notification-bell";
import { useSession } from "./session";
import { roleNames } from "@/lib/types";

const baseNavigation = [
  { href: "/", label: "Yuklar birjasi", icon: Compass },
  { href: "/saved", label: "Saqlangan yuklar", icon: Bookmark },
  { href: "/my-loads", label: "Mening yuklarim", icon: Package },
  { href: "/companies", label: "Kompaniyalarim", icon: Building2 },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useLocale();

  const path = usePathname();
  const { user, logout, loading } = useSession();
  const [menu, setMenu] = useState(false);
  const navigation = [
    ...(user
      ? [
          {
            href: user.role === "driver" ? "/driver" : "/dashboard",
            label:
              user.role === "driver" ? "Haydovchi kabineti" : "Ish kabineti",
            icon: Truck,
          },
        ]
      : []),
    ...(user?.role === "driver"
      ? [
          { href: "/driver/tickets", label: "Tiketlarim", icon: Truck },
          { href: "/notifications", label: "Bildirishnomalar", icon: Compass },
        ]
      : []),
    ...baseNavigation.filter(
      (item) => user?.role !== "driver" || ["/", "/saved"].includes(item.href),
    ),
  ];
  if (path === "/" && (loading || !user)) return <>{children}</>;

  const authPage =
    path === "/login" || path === "/register" || path === "/forgot-password";
  if (authPage)
    return (
      <main className="auth-root">
        <div className="auth-language">
          <LanguageSwitcher />
        </div>
        {children}
      </main>
    );
  const title =
    navigation.find((x) => x.href === path)?.label ||
    (path.startsWith("/loads/new")
      ? t("Yuk joylash")
      : path.startsWith("/loads/")
        ? t("Yuk tafsilotlari")
        : path === "/profile"
          ? t("Mening profilim")
          : t("Boshqaruv"));
  return (
    <div className="app-shell">
      {menu && (
        <button
          className="sidebar-scrim"
          aria-label={t("Menyuni yopish")}
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <Link className="brand" href="/" onClick={() => setMenu(false)}>
          <span className="brand-mark">
            <Route size={25} />
          </span>
          yukflow<span className="brand-dot">.</span>
        </Link>
        <div className="workspace-label">
          {t("YUKLAR. YO‘LLAR. IMKONIYATLAR.")}
        </div>
        <div className="nav-caption">{t("PLATFORMA")}</div>
        <nav aria-label={t("Asosiy menyu")}>
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenu(false)}
              className={`nav-link ${path === item.href ? "active" : ""}`}
            >
              <item.icon size={20} />
              <span>{t(item.label)}</span>
              {path === item.href && <ChevronRight size={16} />}
            </Link>
          ))}
        </nav>
        <Link
          href="/loads/new"
          className="sidebar-post"
          onClick={() => setMenu(false)}
        >
          <Plus size={19} />
          {t("Yuk joylash")}
        </Link>
        <div className="nav-caption account-caption">{t("KABINET")}</div>
        <Link
          href="/profile"
          className={`nav-link ${path === "/profile" ? "active" : ""}`}
          onClick={() => setMenu(false)}
        >
          <Settings2 size={20} />
          {t("Profil va sozlamalar")}
        </Link>
        {user?.is_staff && (
          <Link
            href="/admin"
            className={`nav-link ${path === "/admin" ? "active" : ""}`}
            onClick={() => setMenu(false)}
          >
            <LayoutDashboard size={20} />
            {t("Boshqaruv")}
          </Link>
        )}
        <div className="sidebar-bottom">
          <div className="road-note">
            <Truck size={26} />
            <h4>{t("Yukingizga yo‘l ochamiz.")}</h4>
            <p>{t("Shaxsiy yoki kompaniya nomidan e’lon joylang.")}</p>
            <Link href="/loads/new" onClick={() => setMenu(false)}>
              {t("Boshlash")}
              <ArrowUpRight size={17} />
            </Link>
          </div>
          {user ? (
            <div className="sidebar-user">
              <span className="avatar">
                {(user.first_name || user.username).slice(0, 1).toUpperCase()}
              </span>
              <div>
                <strong>{user.first_name || user.username}</strong>
                <small>{t(roleNames[user.role])}</small>
              </div>
              <button
                className="icon-button"
                aria-label={t("Akkauntdan chiqish")}
                onClick={() =>
                  void logout().catch(() =>
                    alert(t("Chiqishda xatolik. Qayta urinib ko‘ring.")),
                  )
                }
              >
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <div className="sidebar-foot">
              <ShieldCheck size={16} />
              {t("Yo‘lingiz doim ochiq bo‘lsin.")}
            </div>
          )}
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label={t("Menyuni ochish")}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
            <span className="breadcrumb-home">{t("Platforma")}</span>
            <ChevronRight size={14} />
            <strong>{t(title)}</strong>
          </div>
          <div className="topbar-right">
            <NotificationBell />
            <LanguageSwitcher />
            <span className="topbar-divider" />
            {user ? (
              <Link href="/profile" className="top-profile">
                <span className="avatar small">
                  {user.username.slice(0, 1).toUpperCase()}
                </span>
                <span>{user.first_name || user.username}</span>
              </Link>
            ) : (
              <Link href="/login" className="button small-button ghost">
                {t("Kirish")}
                <ArrowUpRight size={16} />
              </Link>
            )}
          </div>
        </header>
        <main className="main-content">{children}</main>
        <footer className="footer">
          <span>© {new Date().getFullYear()} YukFlow</span>
          <span>{t("Yukingiz bor. Yo‘lingiz bor.")}</span>
          <Link href="/loads/new">
            {t("Yuk joylash")}
            <ArrowUpRight size={13} />
          </Link>
        </footer>
      </div>
    </div>
  );
}
