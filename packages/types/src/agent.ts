/**
 * Agent topology types — mirrors the runtime agent topology
 * in workspaces/op1_*/
 */

export type AgentRole =
  | "op1_product"
  | "op1_marketing"
  | "op1_sales"
  | "op1_operations"
  | "op1_manager";

export type AgentStatus = "idle" | "running" | "blocked" | "complete" | "error";

export interface AgentHeartbeat {
  agent: AgentRole;
  status: AgentStatus;
  stage: string;
  lastUpdated: string; // ISO 8601
  currentTask?: string;
  blockedReason?: string;
}
