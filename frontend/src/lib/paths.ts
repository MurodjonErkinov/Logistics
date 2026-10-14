export const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
export const cookiePath = basePath || "/";

export function appPath(path: string) {
  return `${basePath}${path}`;
}
