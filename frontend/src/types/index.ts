export type UserRole = "admin" | "user" | string;

export interface User {
  userId?: string | number | null;
  id?: string | number | null;
  username: string;
  role?: UserRole | null;
  status?: number | string | boolean | null;
  token: string;
  avatar?: string | null;
}

export interface CurrentUser {
  userId?: string | number | null;
  id?: string | number | null;
  username: string;
  role?: UserRole | null;
  status?: number | string | boolean | null;
  avatar?: string | null;
}
