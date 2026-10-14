"use client";
import { useLocale } from "@/components/locale";

import { useEffect, useState } from "react";
import {
  Building2,
  Check,
  ChevronRight,
  Plus,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { Company, Member } from "@/lib/types";
import { Empty, ErrorBox, Field, Loading, Protected } from "@/components/ui";
import { useSession } from "@/components/session";
export default function Companies() {
  return (
    <Protected>
      <Content />
    </Protected>
  );
}
function Content() {
  const { t } = useLocale();

  const { user } = useSession();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selected, setSelected] = useState<Company | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [create, setCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [memberLoading, setMemberLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canManage = selected?.my_role === "owner" || user?.is_staff;
  async function refresh() {
    try {
      setCompanies(await api<Company[]>("partners/companies/?mine=1"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function open(company: Company) {
    setSelected(company);
    setCreate(false);
    setMembers([]);
    setError("");
    setMemberLoading(true);
    try {
      setMembers(
        await api<Member[]>(`partners/companies/${company.id}/members/`),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setMemberLoading(false);
    }
  }
  async function saveCompany(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const company = await api<Company>(
        `partners/companies/${create ? "" : `${selected?.id}/`}`,
        { method: create ? "POST" : "PATCH", body: JSON.stringify(data) },
      );
      setCreate(false);
      await refresh();
      await open(company);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function addMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await api(`partners/companies/${selected.id}/members/`, {
        method: "POST",
        body: JSON.stringify({
          username: data.get("username"),
          role: "member",
          can_post_cargo: data.has("can_post_cargo"),
        }),
      });
      form.reset();
      await open(selected);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function changeMember(member: Member, remove = false) {
    if (!selected) return;
    if (
      remove &&
      !window.confirm(`${member.user_username} kompaniyadan chiqarilsinmi?`)
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`partners/companies/${selected.id}/members/${member.id}/`, {
        method: remove ? "DELETE" : "PATCH",
        ...(remove
          ? {}
          : {
              body: JSON.stringify({ can_post_cargo: !member.can_post_cargo }),
            }),
      });
      await open(selected);
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{t("BIRGA ISHLAYMIZ")}</div>
          <h1>{t("Kompaniyalarim")}</h1>
          <p>
            {t("Jamoangizni birlashtiring. Kompaniya nomidan yuk joylang.")}
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setCreate(true);
            setSelected(null);
            setError("");
          }}
        >
          <Plus size={18} />
          {t("Kompaniya yaratish")}
        </button>
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        <div className="company-layout">
          <div className="company-list">
            {companies.length === 0 && !create ? (
              <Empty
                title={t("Hali kompaniya yo‘q")}
                description={t(
                  "O‘z kompaniyangizni yarating yoki kompaniya egasidan sizni qo‘shishini so‘rang.",
                )}
              />
            ) : (
              companies.map((company) => (
                <button
                  key={company.id}
                  className={`company-card ${selected?.id === company.id ? "selected" : ""}`}
                  onClick={() => void open(company)}
                >
                  <span className="company-icon">
                    <Building2 size={25} />
                  </span>
                  <span>
                    <strong>{company.name}</strong>
                    <small>
                      {company.my_role === "owner"
                        ? t("Kompaniya egasi")
                        : t("Jamoa a’zosi")}
                    </small>
                    {company.can_post_cargo && (
                      <span className="permission-label">
                        <Check size={12} />
                        {t("Yuk joylash ruxsati bor")}
                      </span>
                    )}
                  </span>
                  <ChevronRight size={18} />
                </button>
              ))
            )}
          </div>
          {create || selected ? (
            <div className="company-detail">
              <form
                className="form-section form-stack"
                key={create ? "new" : selected?.id}
                onSubmit={saveCompany}
              >
                <div className="section-title">
                  <h2>
                    {create
                      ? t("Yangi kompaniya")
                      : t("Kompaniya ma’lumotlari")}
                  </h2>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={t("Yopish")}
                    onClick={() => {
                      setCreate(false);
                      setSelected(null);
                    }}
                  >
                    <X size={18} />
                  </button>
                </div>
                <Field label={t("Kompaniya nomi *")}>
                  <input
                    name="name"
                    required
                    maxLength={255}
                    defaultValue={create ? "" : selected?.name}
                    disabled={!create && !canManage}
                  />
                </Field>
                <div className="form-row">
                  <Field label={t("Telefon")}>
                    <input
                      name="phone_number"
                      type="tel"
                      defaultValue={create ? "" : selected?.phone_number}
                      disabled={!create && !canManage}
                      placeholder="+998901234567"
                    />
                  </Field>
                  <Field label="Email">
                    <input
                      name="email"
                      type="email"
                      defaultValue={create ? "" : selected?.email}
                      disabled={!create && !canManage}
                    />
                  </Field>
                </div>
                <Field label={t("Manzil")}>
                  <input
                    name="address"
                    defaultValue={create ? "" : selected?.address}
                    disabled={!create && !canManage}
                  />
                </Field>
                {(create || canManage) && (
                  <button className="button primary" disabled={busy}>
                    {busy
                      ? t("Saqlanmoqda…")
                      : create
                        ? t("Kompaniyani yaratish")
                        : t("Saqlash")}
                  </button>
                )}
              </form>
              {selected && (
                <section className="form-section">
                  <h2>
                    <Users size={20} />
                    {t("Jamoa a’zolari")}
                  </h2>
                  {memberLoading ? (
                    <Loading />
                  ) : (
                    <div className="member-list">
                      {members.map((member) => (
                        <div className="member-row" key={member.id}>
                          <span className="avatar small">
                            {member.user_username.slice(0, 1).toUpperCase()}
                          </span>
                          <div>
                            <strong>{member.user_username}</strong>
                            <small>
                              {member.role === "owner"
                                ? t("Kompaniya egasi")
                                : t("A’zo")}
                            </small>
                          </div>
                          {canManage && member.role !== "owner" ? (
                            <>
                              <label className="checkbox-line">
                                <input
                                  aria-label={`${member.user_username} yuk joylash ruxsati`}
                                  type="checkbox"
                                  checked={member.can_post_cargo}
                                  onChange={() => void changeMember(member)}
                                  disabled={busy}
                                />
                                {t("Yuk joylash")}
                              </label>
                              <button
                                className="icon-button danger"
                                aria-label={`${member.user_username}ni chiqarish`}
                                disabled={busy}
                                onClick={() => void changeMember(member, true)}
                              >
                                <Trash2 size={16} />
                              </button>
                            </>
                          ) : (
                            <span className="permission-label">
                              {member.role === "owner" || member.can_post_cargo
                                ? t("Yuk joylay oladi")
                                : t("Ko‘rish huquqi")}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {canManage && (
                    <form className="add-member" onSubmit={addMember}>
                      <h3>{t("Jamoaga qo‘shish")}</h3>
                      <Field label={t("Foydalanuvchi nomi")}>
                        <input
                          name="username"
                          required
                          placeholder={t("Ro‘yxatdan o‘tgan username")}
                        />
                      </Field>
                      <label className="checkbox-line">
                        <input name="can_post_cargo" type="checkbox" />
                        {t("Yuk joylashga ruxsat berish")}
                      </label>
                      <button className="button secondary" disabled={busy}>
                        <Plus size={17} />
                        {t("A’zo qo‘shish")}
                      </button>
                    </form>
                  )}
                </section>
              )}
            </div>
          ) : companies.length > 0 ? (
            <div className="company-placeholder">
              <Building2 size={40} />
              <h3>{t("Kompaniyani tanlang")}</h3>
              <p>{t("Ma’lumotlar va jamoa a’zolari shu yerda ko‘rinadi.")}</p>
            </div>
          ) : null}
        </div>
      )}
    </>
  );
}
