import { LoadForm } from "@/components/load-form";
export default async function EditLoad({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <LoadForm id={id} />;
}
