"use client";

import type { Load } from "@/lib/types";
import { yandexRoutePoint } from "@/lib/yandex-maps";
import { RouteMap } from "./route-map";

export function LoadRouteMap({ load }: { load: Load }) {
  return (
    <RouteMap
      origin={load.origin}
      destination={load.destination}
      originPoint={yandexRoutePoint(
        load.origin,
        load.origin_lat,
        load.origin_lon,
      )}
      destinationPoint={yandexRoutePoint(
        load.destination,
        load.destination_lat,
        load.destination_lon,
      )}
      className="load-route-map-panel"
    />
  );
}
