"use client";

import { useSession } from "./session";
import { Marketplace } from "./marketplace";
import { Landing } from "./landing";
import { Loading } from "./ui";

export function Home() {
  const { user, loading } = useSession();
  if (loading) return <Loading />;
  return user ? <Marketplace /> : <Landing />;
}
