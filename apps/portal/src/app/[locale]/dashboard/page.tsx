"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card, CardHeader, CardTitle, Badge } from "@op1/ui";
import type { DashboardHealth } from "@op1/api-client";

const DASHBOARD_API = "http://localhost:8765/api";

async function fetchHealth(): Promise<DashboardHealth> {
  const res = await fetch(`${DASHBOARD_API}/health`);
  if (!res.ok) throw new Error(`health: ${res.status}`);
  return res.json() as Promise<DashboardHealth>;
}

type LoadState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "ok"; data: DashboardHealth }
  | { phase: "error"; message: string };

export default function DashboardPage() {
  const t = useTranslations("navigation");
  const tp = useTranslations("portal.dashboard");

  const [state, setState] = useState<LoadState>({ phase: "idle" });

  function load() {
    setState({ phase: "loading" });
    fetchHealth()
      .then((data) => setState({ phase: "ok", data }))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        setState({ phase: "error", message });
      });
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="min-h-screen bg-portal-50 p-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold text-portal-900">{t("dashboard")}</h1>

        <div className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>{tp("systemStatus")}</CardTitle>
            </CardHeader>

            {state.phase === "loading" || state.phase === "idle" ? (
              <p className="mt-4 text-sm text-gray-500">{tp("statusLabel")}…</p>
            ) : state.phase === "error" ? (
              <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-medium text-red-700">{tp("unavailable")}</p>
                <p className="mt-1 text-sm text-red-600">{tp("unavailableHint")}</p>
                <button
                  onClick={load}
                  className="mt-3 text-sm font-medium text-red-700 underline hover:text-red-900"
                >
                  {tp("retryLabel")}
                </button>
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">{tp("statusLabel")}:</span>
                  <Badge
                    variant={
                      state.data.status === "ok"
                        ? "success"
                        : state.data.status === "degraded"
                          ? "warning"
                          : "error"
                    }
                  >
                    {state.data.status === "ok"
                      ? tp("statusOk")
                      : state.data.status === "degraded"
                        ? tp("statusDegraded")
                        : tp("statusError")}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                    <p className="text-xs text-gray-500">{tp("uptime")}</p>
                    <p className="mt-1 text-lg font-semibold text-gray-900">
                      {tp("uptimeSeconds", { seconds: state.data.uptime_seconds })}
                    </p>
                  </div>
                  <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                    <p className="text-xs text-gray-500">{tp("mrr")}</p>
                    <p className="mt-1 text-lg font-semibold text-gray-900">
                      ${state.data.mrr}
                    </p>
                  </div>
                  <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                    <p className="text-xs text-gray-500">{tp("prospectsContacted")}</p>
                    <p className="mt-1 text-lg font-semibold text-gray-900">
                      {state.data.prospects_contacted}
                    </p>
                  </div>
                  <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                    <p className="text-xs text-gray-500">{tp("customersConverted")}</p>
                    <p className="mt-1 text-lg font-semibold text-gray-900">
                      {state.data.customers_converted}
                    </p>
                  </div>
                </div>

                {Object.keys(state.data.services).length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700">{tp("services")}</p>
                    <ul className="mt-2 space-y-1">
                      {Object.entries(state.data.services).map(([name, status]) => (
                        <li key={name} className="flex items-center gap-2 text-sm">
                          <span
                            className={[
                              "inline-block h-2 w-2 rounded-full",
                              status === "up" ? "bg-green-500" : "bg-red-500",
                            ].join(" ")}
                          />
                          <span className="text-gray-700">{name}</span>
                          <span className={status === "up" ? "text-green-700" : "text-red-700"}>
                            {status === "up" ? tp("serviceUp") : tp("serviceDown")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardTitle>{tp("agentStatus")}</CardTitle>
          </Card>
          <Card>
            <CardTitle>{tp("pipelineOverview")}</CardTitle>
          </Card>
          <Card>
            <CardTitle>{tp("kpis")}</CardTitle>
          </Card>
        </div>
      </div>
    </main>
  );
}
