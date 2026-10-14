export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  role: "user" | "driver" | "dispatcher" | "admin";
  is_staff: boolean;
};
export type Load = {
  id: number;
  origin: string;
  destination: string;
  origin_lat?: string | null;
  origin_lon?: string | null;
  destination_lat?: string | null;
  destination_lon?: string | null;
  price_basis?: "trip" | "ton";
  cargo_name: string;
  vehicle_type: string;
  vehicle_kind?: string;
  vehicle_size?: string;
  weight_tons: string;
  is_price_negotiable: boolean;
  price_amount: string | null;
  currency: string;
  contact_phone: string;
  alternate_phone: string;
  pickup_date: string | null;
  notes: string;
  status: "open" | "closed";
  posted_by: number;
  posted_by_username: string;
  company: number | null;
  company_name?: string;
  source_url: string | null;
  created_at: string;
  updated_at: string;
};
export type Company = {
  id: number;
  name: string;
  phone_number: string;
  email: string;
  address: string;
  my_role: "owner" | "member" | null;
  can_post_cargo: boolean;
};
export type Member = {
  id: number;
  user_id: number;
  user_username: string;
  role: "owner" | "member";
  can_post_cargo: boolean;
};
export const roleNames: Record<User["role"], string> = {
  user: "Yuk jo‘natuvchi",
  driver: "Haydovchi",
  dispatcher: "Dispetcher",
  admin: "Administrator",
};
