export type HandoffStatus =
  | "ready_for_marketing_review"
  | "ready_for_sales_review"
  | "ready_for_operations_review"
  | "pending"
  | "complete";

export interface HandoffMetadata {
  contract_version: string;
  generated_at: string;
  generated_by: string;
}

export interface HandoffPositioning {
  headline: string;
  value_proposition: string;
}

export interface HandoffConstraints {
  budget: number;
  timeline_days: number;
  out_of_scope: string[];
}

export interface HandoffPayload extends HandoffMetadata {
  status: HandoffStatus;
  idea_name: string;
  icp: string;
  problem: string;
  mvp_scope: string[];
  landing_page_url_or_path: string;
  positioning: HandoffPositioning;
  constraints: HandoffConstraints;
  notes: string;
}

export interface DashboardHealth {
  status: "ok" | "degraded" | "error";
  uptime_seconds: number;
  services: Record<string, "up" | "down">;
  mrr: number;
  prospects_contacted: number;
  customers_converted: number;
}

export interface HandoffSummary {
  id: string;
  status: HandoffStatus;
  generated_at: string;
  idea_name: string;
}

export interface GetHandoffsResponse {
  handoffs: HandoffSummary[];
  total: number;
}

export interface GetHandoffStatusResponse {
  handoff_id: string;
  status: HandoffStatus;
  generated_at: string;
}
