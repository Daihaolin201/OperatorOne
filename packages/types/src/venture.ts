/**
 * Venture / opportunity types — used by Studio and Dashboard
 */

export type VentureStage =
  | "discovery"
  | "validation"
  | "build"
  | "launch"
  | "growth"
  | "exit";

export type VentureStatus = "active" | "paused" | "archived" | "killed";

export interface Venture {
  id: string;
  name: string;
  description: string;
  stage: VentureStage;
  status: VentureStatus;
  targetMrr: number;
  currentMrr: number;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

export interface Opportunity {
  id: string;
  ventureId: string;
  title: string;
  problem: string;
  solution: string;
  score: number; // 0–100
  tags: string[];
  createdAt: string;
}
