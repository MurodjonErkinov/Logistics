"use client";
import { useEffect, useState } from "react";
import { useSession } from "./session";

export function useSaved() {
  const { user, loading } = useSession();
  const key = `yukflow-saved-${user?.id ?? "guest"}`;
  const [saved, setSaved] = useState<number[]>([]);
  useEffect(() => {
    if (loading) return;
    try {
      const value: unknown = JSON.parse(localStorage.getItem(key) || "[]");
      setSaved(
        Array.isArray(value)
          ? value.filter((x): x is number => typeof x === "number")
          : [],
      );
    } catch {
      setSaved([]);
    }
  }, [key, loading]);
  function toggle(id: number) {
    setSaved((current) => {
      const next = current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id];
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {}
      return next;
    });
  }
  return { saved, toggle };
}
