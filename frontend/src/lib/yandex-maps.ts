export function yandexRoutePoint(
  name: string,
  lat?: string | number | null,
  lon?: string | number | null,
) {
  if (lat != null && lon != null && lat !== "" && lon !== "") {
    const latitude = Number(lat),
      longitude = Number(lon);
    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude) &&
      Math.abs(latitude) <= 90 &&
      Math.abs(longitude) <= 180
    )
      return `${latitude},${longitude}`;
  }
  return name.replaceAll("~", " ").trim();
}

export function yandexRouteUrls(
  origin: string,
  destination: string,
  locale: "uz" | "ru",
) {
  const params = new URLSearchParams({
    rtext: `${origin.replaceAll("~", " ")}~${destination.replaceAll("~", " ")}`,
    rtt: "auto",
    mode: "routes",
    lang: locale === "ru" ? "ru_RU" : "en_US",
  });
  return {
    embed: `https://yandex.com/map-widget/v1/?${params}`,
    external: `https://yandex.com/maps/?${params}`,
  };
}
