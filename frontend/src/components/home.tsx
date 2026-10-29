"use client";

import { useSession } from "./session";
import { Marketplace } from "./marketplace";
import { Landing } from "./landing";

export function Home() {
  const { user } = useSession();
  return user ? <Marketplace /> : <Landing />;
}
