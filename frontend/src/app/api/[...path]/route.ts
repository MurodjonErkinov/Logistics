import { cookiePath } from "@/lib/paths";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8018").replace(
  /\/$/,
  "",
);
type Tokens = { access: string; refresh?: string };
const refreshes = new Map<string, Promise<Tokens | null>>();

function setTokens(
  response: NextResponse,
  tokens: Tokens,
  request: NextRequest,
) {
  const options = {
    httpOnly: true,
    sameSite: "lax" as const,
    secure:
      process.env.NODE_ENV === "production" ||
      request.nextUrl.protocol === "https:",
    path: cookiePath,
  };
  response.cookies.set("yf_access", tokens.access, {
    ...options,
    maxAge: 15 * 60,
  });
  if (tokens.refresh)
    response.cookies.set("yf_refresh", tokens.refresh, {
      ...options,
      maxAge: 7 * 86400,
    });
}
function clearTokens(response: NextResponse) {
  response.cookies.set("yf_access", "", { path: cookiePath, maxAge: 0 });
  response.cookies.set("yf_refresh", "", { path: cookiePath, maxAge: 0 });
}
async function renew(
  refresh: string,
  address: string | null,
): Promise<Tokens | null> {
  if (!refreshes.has(refresh)) {
    const promise = fetch(`${backend}/api/auth/refresh/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-Proto":
          process.env.NODE_ENV === "production" ? "https" : "http",
        ...(address ? { "X-Forwarded-For": address } : {}),
      },
      body: JSON.stringify({ refresh }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    }).then(async (r) => (r.ok ? ((await r.json()) as Tokens) : null));
    refreshes.set(refresh, promise);
    setTimeout(() => refreshes.delete(refresh), 15000).unref();
  }
  return refreshes.get(refresh)!;
}
async function handle(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const route = path.join("/");
  if (
    !/^(auth\/(login|register|logout|me|users(?:\/\d+)?)|cargo\/loads(?:\/\d+)?|driver\/(?:vehicles(?:\/\d+)?|tickets(?:\/\d+(?:\/return-trip)?)?|notifications(?:\/(?:unread|read-all|\d+(?:\/(?:read|dismiss))?))?|preferences|telegram-link)|partners\/companies(?:\/\d+(?:\/members(?:\/\d+)?)?)?)$/.test(
      route,
    )
  ) {
    return NextResponse.json({ detail: "Sahifa topilmadi." }, { status: 404 });
  }
  if (
    ["auth/login", "auth/register", "auth/logout"].includes(route) &&
    request.method !== "POST"
  ) {
    return NextResponse.json(
      { detail: "Bu amal POST so‘rovini talab qiladi." },
      { status: 405 },
    );
  }
  if (!["GET", "HEAD"].includes(request.method)) {
    const origin = request.headers.get("origin");
    let validOrigin = false;
    try {
      validOrigin = Boolean(
        origin &&
        new URL(origin).host === request.headers.get("host") &&
        new URL(origin).protocol === request.nextUrl.protocol &&
        (!process.env.PUBLIC_SITE_URL ||
          new URL(origin).origin ===
            new URL(process.env.PUBLIC_SITE_URL).origin),
      );
    } catch {}
    if (!validOrigin) {
      return NextResponse.json(
        { detail: "So‘rov manbasi tasdiqlanmadi." },
        { status: 403 },
      );
    }
  }
  if (
    !["GET", "HEAD"].includes(request.method) &&
    !request.headers
      .get("content-type")
      ?.toLowerCase()
      .startsWith("application/json")
  ) {
    return NextResponse.json(
      { detail: "JSON formatida yuboring." },
      { status: 415 },
    );
  }
  try {
    let body: string | undefined;
    if (!["GET", "HEAD"].includes(request.method)) {
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 65536) {
            await reader.cancel();
            return NextResponse.json(
              { detail: "So‘rov hajmi 64 KB dan oshmasin." },
              { status: 413 },
            );
          }
          chunks.push(value);
        }
      }
      body = Buffer.concat(chunks).toString("utf8");
    }
    const refresh = request.cookies.get("yf_refresh")?.value;
    let access = request.cookies.get("yf_access")?.value;
    let renewed: Tokens | null = null;
    const anonymous = route === "auth/login" || route === "auth/register";
    if (!anonymous && !access && refresh) {
      renewed = await renew(refresh, request.headers.get("x-real-ip"));
      access = renewed?.access;
    }
    if (route === "auth/logout")
      body = JSON.stringify({ refresh: renewed?.refresh || refresh });
    const send = () =>
      fetch(`${backend}/api/${route}/${request.nextUrl.search}`, {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          "X-Forwarded-Proto":
            process.env.NODE_ENV === "production" ? "https" : "http",
          ...(request.headers.get("x-real-ip")
            ? { "X-Forwarded-For": request.headers.get("x-real-ip")! }
            : {}),
          ...(access && !anonymous
            ? { Authorization: `Bearer ${access}` }
            : {}),
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
      });
    let upstream = await send();
    if (upstream.status === 401 && refresh && !anonymous && !renewed) {
      renewed = await renew(refresh, request.headers.get("x-real-ip"));
      if (renewed) {
        access = renewed.access;
        if (route === "auth/logout")
          body = JSON.stringify({ refresh: renewed.refresh || refresh });
        upstream = await send();
      }
    }
    if (route === "auth/logout") {
      const response = new NextResponse(null, { status: 204 });
      clearTokens(response);
      return response;
    }
    const data = upstream.status === 204 ? null : await upstream.json();
    const response =
      upstream.status === 204
        ? new NextResponse(null, { status: 204 })
        : NextResponse.json(
            route === "auth/login" && upstream.ok ? { success: true } : data,
            { status: upstream.status },
          );
    response.headers.set("Cache-Control", "no-store");
    if (route === "auth/me" && upstream.ok && body && JSON.parse(body).password)
      clearTokens(response);
    else if (route === "auth/login" && upstream.ok)
      setTokens(response, data, request);
    else if (renewed) setTokens(response, renewed, request);
    else if (upstream.status === 401) clearTokens(response);
    return response;
  } catch {
    return NextResponse.json(
      {
        detail:
          "Server bilan aloqa uzildi. Birozdan keyin qayta urinib ko‘ring.",
      },
      { status: 502 },
    );
  }
}
export {
  handle as GET,
  handle as POST,
  handle as PATCH,
  handle as PUT,
  handle as DELETE,
};
