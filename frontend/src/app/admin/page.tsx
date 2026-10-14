"use client";
import { useLocale } from "@/components/locale";

import { useEffect, useState } from "react";
import { Search, ShieldCheck } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { roleNames, type User } from "@/lib/types";
import { useSession } from "@/components/session";
import { Empty, ErrorBox, Loading, Protected } from "@/components/ui";
export default function Admin() {
  return (
    <Protected>
      <Content />
    </Protected>
  );
}
function Content() {
  const { t } = useLocale();

  const { user } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => {
    if (!user?.is_staff) {
      setLoading(false);
      return;
    }
    api<User[]>("auth/users/")
      .then(setUsers)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, [user?.is_staff]);
  async function changeRole(target: User, role: string) {
    setBusy(target.id);
    setError("");
    try {
      const updated = await api<User>(`auth/users/${target.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      setUsers((current) =>
        current.map((x) => (x.id === updated.id ? updated : x)),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }
  if (!user?.is_staff)
    return (
      <Empty
        title={t("Bu bo‘lim administrator uchun")}
        description={t("Sizning akkauntingizda boshqaruv huquqi yo‘q.")}
      />
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{t("ADMINISTRATOR")}</div>
          <h1>{t("Foydalanuvchilar")}</h1>
          <p>{t("Akkauntlar va platformadagi rollarni boshqaring.")}</p>
        </div>
        <span className="admin-chip">
          <ShieldCheck size={17} />
          {t("Boshqaruv")}
        </span>
      </div>
      <div className="admin-search">
        <Search size={18} />
        <input
          aria-label={t("Foydalanuvchini qidirish")}
          placeholder={t("Username yoki ism bo‘yicha qidirish")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("Foydalanuvchi")}</th>
                <th>{t("Telefon")}</th>
                <th>{t("Rol")}</th>
                <th>{t("Huquq")}</th>
              </tr>
            </thead>
            <tbody>
              {users
                .filter((u) =>
                  `${u.username} ${u.first_name} ${u.last_name}`
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((u) => (
                  <tr key={u.id}>
                    <td>
                      <strong>
                        {u.first_name || u.username} {u.last_name}
                      </strong>
                      <small>@{u.username}</small>
                    </td>
                    <td>{u.phone_number || "—"}</td>
                    <td>
                      <select
                        aria-label={`${u.username} roli`}
                        value={u.role}
                        disabled={busy === u.id}
                        onChange={(e) => void changeRole(u, e.target.value)}
                      >
                        {Object.entries(roleNames).map(([value, name]) => (
                          <option key={value} value={value}>
                            {t(name)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      {u.is_staff
                        ? t("Administrator huquqi")
                        : t("Oddiy akkaunt")}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="field-note">
        {t(
          "Rolni o‘zgartirish administrator huquqini avtomatik bermaydi. Administrator huquqi Django admin orqali boshqariladi.",
        )}
      </p>
    </>
  );
}
