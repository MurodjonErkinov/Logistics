"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

type Session = {
  user: User | null;
  loading: boolean;
  reload: () => Promise<User | null>;
  logout: () => Promise<void>;
};
const Context = createContext<Session>({
  user: null,
  loading: true,
  reload: async () => null,
  logout: async () => {},
});
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try {
      const value = await api<User>("auth/me/");
      setUser(value);
      return value;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);
  async function logout() {
    await api("auth/logout/", { method: "POST", body: "{}" });
    setUser(null);
    window.location.assign("/");
  }
  return (
    <Context.Provider value={{ user, loading, reload, logout }}>
      {children}
    </Context.Provider>
  );
}
export const useSession = () => useContext(Context);
