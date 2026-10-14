import { LoadDetail } from "@/components/load-detail";
export default async function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <LoadDetail id={id} />;
}
