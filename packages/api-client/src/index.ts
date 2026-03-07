import type {
  DashboardHealth,
  GetHandoffStatusResponse,
  GetHandoffsResponse,
  HandoffPayload,
} from "./types.js";

export type * from "./types.js";

const DEFAULT_BASE_URL = "/api";

function baseUrl(): string {
  if (typeof window !== "undefined") {
    return (window as { __OP1_API_BASE__?: string }).__OP1_API_BASE__ ?? DEFAULT_BASE_URL;
  }
  return DEFAULT_BASE_URL;
}

export async function getDashboardHealth(): Promise<DashboardHealth> {
  const res = await fetch(`${baseUrl()}/health`);
  if (!res.ok) throw new Error(`getDashboardHealth: ${res.status}`);
  return res.json() as Promise<DashboardHealth>;
}

export async function getHandoffStatus(handoffId: string): Promise<GetHandoffStatusResponse> {
  const res = await fetch(`${baseUrl()}/handoffs/${encodeURIComponent(handoffId)}/status`);
  if (!res.ok) throw new Error(`getHandoffStatus: ${res.status}`);
  return res.json() as Promise<GetHandoffStatusResponse>;
}

export async function getHandoffs(): Promise<GetHandoffsResponse> {
  const res = await fetch(`${baseUrl()}/handoffs`);
  if (!res.ok) throw new Error(`getHandoffs: ${res.status}`);
  return res.json() as Promise<GetHandoffsResponse>;
}

export async function getHandoff(handoffId: string): Promise<HandoffPayload> {
  const res = await fetch(`${baseUrl()}/handoffs/${encodeURIComponent(handoffId)}`);
  if (!res.ok) throw new Error(`getHandoff: ${res.status}`);
  return res.json() as Promise<HandoffPayload>;
}
