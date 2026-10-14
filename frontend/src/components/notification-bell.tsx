"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { api } from "@/lib/api";
import { useSession } from "./session";
import { useLocale } from "./locale";

export function NotificationBell() {
  const { user } = useSession();
  const { t } = useLocale();
  const [count, setCount] = useState(0);
  useEffect(() => {
    let alive = true;
    setCount(0);
    if (user?.role !== "driver") return;
    async function refresh() {
      try {
        const result = await api<{ count: number }>(
          "driver/notifications/unread/",
        );
        if (alive) setCount(result.count);
      } catch {}
    }
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 30000);
    window.addEventListener("driver-notifications", refresh);
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("driver-notifications", refresh);
    };
  }, [user?.id, user?.role]);
  return user?.role === "driver" ? (
    <Link
      href="/notifications"
      className="notification-bell"
      aria-label={`${t("Bildirishnomalar")}: ${count}`}
    >
      <Bell size={21} />
      {count > 0 && <span>{count > 99 ? "99+" : count}</span>}
    </Link>
  ) : null;
}
