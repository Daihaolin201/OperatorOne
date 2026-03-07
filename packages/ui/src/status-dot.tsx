import * as React from "react";
import type { AgentStatus } from "@op1/types";

export interface StatusDotProps {
  status: AgentStatus;
  label?: string;
  showLabel?: boolean;
}

const statusClasses: Record<AgentStatus, string> = {
  idle: "bg-gray-400",
  running: "bg-green-500 animate-pulse",
  blocked: "bg-yellow-500",
  complete: "bg-blue-500",
  error: "bg-red-500",
};

const statusLabels: Record<AgentStatus, string> = {
  idle: "Idle",
  running: "Running",
  blocked: "Blocked",
  complete: "Complete",
  error: "Error",
};

export function StatusDot({ status, label, showLabel = false }: StatusDotProps) {
  const displayLabel = label ?? statusLabels[status];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={["inline-block h-2 w-2 rounded-full", statusClasses[status]].join(" ")}
        aria-hidden="true"
      />
      {showLabel && (
        <span className="text-sm text-gray-600">{displayLabel}</span>
      )}
    </span>
  );
}
