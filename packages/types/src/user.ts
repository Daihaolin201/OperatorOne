/**
 * User types — shared between portal (internal) and product (external)
 * Portal users are internal operators; product users are external customers.
 */

export type UserRole = "admin" | "operator" | "viewer";

export interface User {
  id: string;
  email: string;
  displayName: string;
  role: UserRole;
  locale: "en" | "zh";
  createdAt: string;
}

export interface Session {
  userId: string;
  token: string;
  expiresAt: string;
}
