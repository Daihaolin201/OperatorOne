#!/usr/bin/env python3
"""Multi-agent CEO orchestrator v1.

Purpose:
- orchestrate Product/Marketing/Sales/Operations via OpenClaw agent calls
- keep a full, auditable run log
- produce a compact operator-facing summary artifact
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
CEO_WS = Path(__file__).resolve().parents[1]
OUT_DIR = CEO_WS / "research" / "ceo_orchestration"
RUN_PATH = OUT_DIR / "run.latest.json"
SUMMARY_PATH = OUT_DIR / "orchestrator_summary.latest.json"
APPROVAL_PATH = OUT_DIR / "approval.json"

OPENCLAW_PROFILE = "operatorone"


@dataclass
class AgentTurn:
    agent_id: str
    objective: str
    ok: bool
    code: int
    reply: str
    started_at: str
    ended_at: str
    duration_ms: int
    stdout_tail: str
    stderr_tail: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    start = raw.find("{")
    while start >= 0:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start : i + 1]
                    try:
                        data = json.loads(candidate)
                        return data if isinstance(data, dict) else None
                    except Exception:
                        break
        start = raw.find("{", start + 1)
    return None


def parse_reply_text(payload: Optional[Dict[str, Any]], fallback: str) -> str:
    if isinstance(payload, dict):
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
        for item in payloads:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                return item["text"].strip()[:2000]
    return (fallback or "").strip()[-2000:]


def approval_granted(path: Path) -> bool:
    payload = read_json(path, {})
    return bool(isinstance(payload, dict) and payload.get("approve_external_actions") is True)


def run_agent_turn(agent_id: str, objective: str, timeout_sec: int = 120, dry_run: bool = False) -> AgentTurn:
    started = datetime.now(timezone.utc)
    if dry_run:
        ended = datetime.now(timezone.utc)
        return AgentTurn(
            agent_id=agent_id,
            objective=objective,
            ok=True,
            code=0,
            reply=f"[dry-run] objective queued for {agent_id}",
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
            duration_ms=int((ended - started).total_seconds() * 1000),
            stdout_tail="",
            stderr_tail="",
        )

    cmd = [
        "openclaw",
        "--profile",
        OPENCLAW_PROFILE,
        "agent",
        "--agent",
        agent_id,
        "--message",
        objective,
        "--timeout",
        str(timeout_sec),
        "--json",
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    ended = datetime.now(timezone.utc)
    payload = extract_json(proc.stdout)
    reply = parse_reply_text(payload, proc.stdout)

    return AgentTurn(
        agent_id=agent_id,
        objective=objective,
        ok=(proc.returncode == 0),
        code=proc.returncode,
        reply=reply,
        started_at=started.isoformat(),
        ended_at=ended.isoformat(),
        duration_ms=int((ended - started).total_seconds() * 1000),
        stdout_tail=(proc.stdout or "")[-1200:],
        stderr_tail=(proc.stderr or "")[-1200:],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CEO multi-agent orchestrator v1")
    parser.add_argument("--goal", default="Reach first $100 MRR with disciplined experimentation")
    parser.add_argument("--target-mrr", type=int, default=100)
    parser.add_argument("--max-days", type=int, default=14)
    parser.add_argument("--max-spend", type=int, default=200)
    parser.add_argument("--require-approval", dest="require_approval", action="store_true", default=True)
    parser.add_argument("--no-require-approval", dest="require_approval", action="store_false")
    parser.add_argument("--approval-file", default=str(APPROVAL_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    approval_file = Path(args.approval_file)
    approved = args.dry_run or (not args.require_approval) or approval_granted(approval_file)

    turns: List[AgentTurn] = []
    status = "completed"

    mission_brief = {
        "goal": args.goal,
        "constraints": {
            "target_mrr_usd": args.target_mrr,
            "max_days": args.max_days,
            "max_cash_spend_usd": args.max_spend,
        },
        "policy": {
            "require_approval_for_external_actions": args.require_approval,
            "approval_granted": approved,
        },
    }

    if not approved:
        status = "waiting_approval"
    else:
        prompts = [
            (
                "op1_product",
                f"""You are the Product specialist. Mission goal: {args.goal}\n"
                f"Constraints: target_mrr_usd={args.target_mrr}, max_days={args.max_days}, max_cash_spend_usd={args.max_spend}.\n"
                "Return concise output with:\n"
                "1) selected opportunity id\n2) why this is best now\n3) next executable product step."
                """,
            ),
            (
                "op1_marketing",
                "Based on Product direction, provide 3 channel-light GTM experiments for first 14 days. "
                "Return: experiment, expected signal, fail threshold.",
            ),
            (
                "op1_sales",
                "Provide minimal early sales motion for first $100 MRR. "
                "Return: target segment, outreach opener, qualification rule, close trigger.",
            ),
            (
                "op1_operations",
                "Provide weekly operating cadence and KPI board for this venture. "
                "Return: KPI list, daily check, weekly review, rollback conditions.",
            ),
        ]

        for agent_id, objective in prompts:
            turn = run_agent_turn(agent_id=agent_id, objective=objective, timeout_sec=150, dry_run=args.dry_run)
            turns.append(turn)
            if not turn.ok:
                status = "failed"
                break

    summary = {
        "generated_at": now_iso(),
        "goal": args.goal,
        "status": status,
        "approval": {
            "required": args.require_approval,
            "granted": approved,
            "approval_file": str(Path(args.approval_file)),
        },
        "agent_outcomes": [
            {
                "agent_id": t.agent_id,
                "ok": t.ok,
                "reply": t.reply,
            }
            for t in turns
        ],
    }

    run_payload = {
        "contract": "ceo_multi_agent_orchestrator.v1",
        "generated_at": now_iso(),
        "mission": mission_brief,
        "status": status,
        "steps": [
            {
                "agent_id": t.agent_id,
                "objective": t.objective,
                "ok": t.ok,
                "code": t.code,
                "reply": t.reply,
                "started_at": t.started_at,
                "ended_at": t.ended_at,
                "duration_ms": t.duration_ms,
                "stdout_tail": t.stdout_tail,
                "stderr_tail": t.stderr_tail,
            }
            for t in turns
        ],
    }

    RUN_PATH.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "status": status, "run": str(RUN_PATH), "summary": str(SUMMARY_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
