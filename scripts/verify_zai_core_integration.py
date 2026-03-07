#!/usr/bin/env python3
"""Verify that OperatorOne uses Z.AI GLM as a core runtime component.

Checks performed:
1) Repository manifest default model/fallback expectations.
2) Active profile config alignment with manifest expectations.
3) Optional live agent probes to confirm provider/model in runtime metadata.

The report intentionally avoids printing secrets (API key value is never emitted).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CmdResult:
    code: int
    stdout: str
    stderr: str


class VerifyError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(cmd: List[str], cwd: Path, timeout: int = 90) -> CmdResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CmdResult(code=proc.returncode, stdout=proc.stdout or "", stderr=proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return CmdResult(
            code=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=((exc.stderr or "") if isinstance(exc.stderr, str) else "") + f"\nTIMEOUT after {timeout}s",
        )


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    n = len(text)
    for start in range(n):
        if text[start] != "{":
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, n):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        break
    return None


def parse_last_line_path(text: str) -> Optional[Path]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    maybe = lines[-1]
    if maybe.startswith("~"):
        return Path(maybe).expanduser().resolve()
    p = Path(maybe)
    if p.is_absolute() or "/" in maybe:
        return p.expanduser().resolve()
    return None


def get_profile_config_path(repo_root: Path, profile: str) -> Optional[Path]:
    res = run_cmd(["openclaw", "--profile", profile, "config", "file"], cwd=repo_root, timeout=30)
    if res.code != 0:
        return None
    return parse_last_line_path(res.stdout)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def apply_fallbacks(repo_root: Path, profile: str, fallbacks: List[str]) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    clear_res = run_cmd(["openclaw", "--profile", profile, "models", "fallbacks", "clear"], cwd=repo_root, timeout=45)
    steps.append(
        {
            "action": "clear",
            "ok": clear_res.code == 0,
            "code": clear_res.code,
            "stderrTail": (clear_res.stderr or "")[-240:],
        }
    )
    if clear_res.code != 0:
        return {"ok": False, "steps": steps}

    for fb in fallbacks:
        add_res = run_cmd(
            ["openclaw", "--profile", profile, "models", "fallbacks", "add", fb],
            cwd=repo_root,
            timeout=45,
        )
        steps.append(
            {
                "action": "add",
                "model": fb,
                "ok": add_res.code == 0,
                "code": add_res.code,
                "stderrTail": (add_res.stderr or "")[-240:],
            }
        )
        if add_res.code != 0:
            return {"ok": False, "steps": steps}

    return {"ok": True, "steps": steps}


def probe_agent(repo_root: Path, profile: str, agent_id: str, timeout: int) -> Dict[str, Any]:
    prompt = {
        "kind": "zai_core_probe.v1",
        "request": "Reply with compact JSON only: {ack:true,agent:'<id>',status:'ok'}",
        "agent": agent_id,
    }
    session_id = f"zai-probe-{agent_id}-{int(time.time() * 1000)}"
    cmd = [
        "openclaw",
        "--profile",
        profile,
        "agent",
        "--agent",
        agent_id,
        "--session-id",
        session_id,
        "--message",
        json.dumps(prompt, ensure_ascii=False),
        "--timeout",
        str(max(20, int(timeout))),
        "--json",
    ]
    res = run_cmd(cmd, cwd=repo_root, timeout=max(timeout + 30, 60))
    payload = extract_json_object(res.stdout)

    result = {
        "agentId": agent_id,
        "sessionId": session_id,
        "ok": res.code == 0,
        "exitCode": res.code,
        "provider": None,
        "model": None,
        "durationMs": None,
        "usage": {},
        "responseText": None,
        "stderrTail": (res.stderr or "")[-300:],
    }

    if isinstance(payload, dict):
        meta = ((payload.get("result") or {}).get("meta") or {})
        agent_meta = meta.get("agentMeta") or {}
        result["provider"] = agent_meta.get("provider")
        result["model"] = agent_meta.get("model")
        result["durationMs"] = meta.get("durationMs")
        usage = agent_meta.get("lastCallUsage") or agent_meta.get("usage") or {}
        result["usage"] = usage if isinstance(usage, dict) else {}

        text_payloads = ((payload.get("result") or {}).get("payloads") or [])
        if isinstance(text_payloads, list) and text_payloads:
            first = text_payloads[0] or {}
            if isinstance(first, dict):
                txt = first.get("text")
                if isinstance(txt, str):
                    result["responseText"] = txt[:400]

    provider = str(result.get("provider") or "").strip().lower()
    model = str(result.get("model") or "").strip().lower()
    result["zaiCompliant"] = bool(result["ok"] and provider == "zai" and model.startswith("glm-"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Z.AI GLM core integration for OperatorOne")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--profile", default="operatorone", help="OpenClaw profile name")
    parser.add_argument("--probe-all-agents", action="store_true", help="Probe all manifest agents")
    parser.add_argument("--probe-agent", action="append", default=[], help="Probe specific agent id (repeatable)")
    parser.add_argument("--probe-timeout", type=int, default=60, help="Per-agent probe timeout seconds")
    parser.add_argument(
        "--probe-without-fallback",
        action="store_true",
        help="Temporarily clear model fallbacks during runtime probes, then restore",
    )
    parser.add_argument(
        "--report-path",
        default="docs/evidence/zai/core_integration_report.latest.json",
        help="Where to write JSON report",
    )
    parser.add_argument("--no-write", action="store_true", help="Do not write report file")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    manifest_path = repo_root / "openclaw" / "agents.manifest.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict):
        raise VerifyError(f"Invalid manifest JSON: {manifest_path}")

    expected_primary = str(manifest.get("profileDefaultModel") or "").strip()
    expected_fallbacks = [str(x).strip() for x in (manifest.get("profileModelFallbacks") or []) if str(x).strip()]
    manifest_agents = [
        str(x.get("id") or "").strip()
        for x in (manifest.get("agents") or [])
        if isinstance(x, dict) and str(x.get("id") or "").strip()
    ]

    config_path = get_profile_config_path(repo_root, args.profile)
    config = load_json(config_path, {}) if config_path else {}

    defaults = (((config.get("agents") or {}).get("defaults") or {}).get("model") or {}) if isinstance(config, dict) else {}
    actual_primary = str(defaults.get("primary") or "").strip()
    raw_fallbacks = defaults.get("fallbacks")
    if isinstance(raw_fallbacks, list):
        actual_fallbacks = [str(x).strip() for x in raw_fallbacks if str(x).strip()]
    elif isinstance(raw_fallbacks, str) and raw_fallbacks.strip():
        actual_fallbacks = [raw_fallbacks.strip()]
    else:
        actual_fallbacks = []

    env_cfg = (config.get("env") or {}) if isinstance(config, dict) else {}
    zai_key = env_cfg.get("ZAI_API_KEY")
    has_zai_key = isinstance(zai_key, str) and bool(zai_key.strip())

    checks = {
        "manifest_primary_is_zai": expected_primary.startswith("zai/"),
        "manifest_primary_is_glm_family": expected_primary.startswith("zai/glm-"),
        "config_path_found": bool(config_path),
        "config_primary_matches_manifest": bool(expected_primary and actual_primary == expected_primary),
        "config_primary_is_zai": actual_primary.startswith("zai/"),
        "config_fallbacks_match_manifest": actual_fallbacks == expected_fallbacks if expected_fallbacks else True,
        "zai_api_key_present": has_zai_key,
    }

    probes: List[Dict[str, Any]] = []
    probe_targets: List[str] = []
    if args.probe_all_agents:
        probe_targets.extend(manifest_agents)
    probe_targets.extend([x for x in args.probe_agent if x])

    # Deduplicate while preserving order.
    seen = set()
    unique_targets = []
    for aid in probe_targets:
        if aid in seen:
            continue
        seen.add(aid)
        unique_targets.append(aid)

    probe_policy = {
        "withoutFallback": bool(args.probe_without_fallback),
        "fallbacksBeforeProbe": actual_fallbacks,
        "fallbackMutation": None,
        "fallbackRestore": None,
    }

    if unique_targets and args.probe_without_fallback:
        probe_policy["fallbackMutation"] = apply_fallbacks(repo_root, args.profile, [])

    try:
        for aid in unique_targets:
            probes.append(probe_agent(repo_root, args.profile, aid, timeout=args.probe_timeout))
    finally:
        if unique_targets and args.probe_without_fallback:
            probe_policy["fallbackRestore"] = apply_fallbacks(repo_root, args.profile, actual_fallbacks)

    probe_ok = True
    if probes:
        probe_ok = all(bool(row.get("zaiCompliant")) for row in probes)
        checks["runtime_probe_all_zai"] = probe_ok
    else:
        checks["runtime_probe_all_zai"] = None

    all_pass = all(v is True for v in checks.values() if v is not None)

    non_compliant_agents = [
        str(row.get("agentId") or "")
        for row in probes
        if row and not bool(row.get("zaiCompliant"))
    ]
    probe_any_zai = any(str((row or {}).get("provider") or "").strip().lower() == "zai" for row in probes)

    report = {
        "generatedAt": now_iso(),
        "repoRoot": str(repo_root),
        "profile": args.profile,
        "manifest": {
            "path": str(manifest_path),
            "expectedPrimary": expected_primary,
            "expectedFallbacks": expected_fallbacks,
            "agents": manifest_agents,
        },
        "profileConfig": {
            "path": str(config_path) if config_path else None,
            "actualPrimary": actual_primary,
            "actualFallbacks": actual_fallbacks,
            "hasZaiApiKey": has_zai_key,
        },
        "checks": checks,
        "probePolicy": probe_policy,
        "runtimeProbes": probes,
        "summary": {
            "ok": all_pass,
            "probeCount": len(probes),
            "probeZaiCompliant": probe_ok,
            "probeAnyZai": probe_any_zai,
            "nonCompliantAgents": non_compliant_agents,
        },
    }

    if not args.no_write:
        report_path = Path(args.report_path)
        if not report_path.is_absolute():
            report_path = repo_root / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
