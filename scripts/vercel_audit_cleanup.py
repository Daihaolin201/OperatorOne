#!/usr/bin/env python3
"""Audit/cleanup helper for Vercel project governance.

Default mode is dry-run audit only.
Use --apply to execute removals for candidates.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "dashboard" / ".runtime" / "studio"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_first_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty output")
    try:
        return json.loads(text)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[i:])
            return payload
        except Exception:
            continue
    raise ValueError("no JSON payload found")


def run(cmd: List[str], timeout: int = 60) -> Dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=timeout)
    raw = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    out: Dict[str, Any] = {"ok": proc.returncode == 0, "code": proc.returncode, "cmd": cmd, "raw": raw[:4000]}
    if raw:
        try:
            out["json"] = parse_first_json(raw)
        except Exception:
            pass
    return out


def vercel_projects_json() -> Dict[str, Any]:
    # try known command variants
    candidates = [
        ["vercel", "project", "ls", "--json"],
        ["vercel", "projects", "ls", "--json"],
    ]
    attempts = []
    for cmd in candidates:
        result = run(cmd, timeout=90)
        attempts.append(result)
        if result.get("ok") and result.get("json") is not None:
            payload = result.get("json")
            # normalize array
            projects = []
            if isinstance(payload, list):
                projects = payload
            elif isinstance(payload, dict):
                for key in ["projects", "items"]:
                    if isinstance(payload.get(key), list):
                        projects = payload.get(key)
                        break
                if not projects:
                    # maybe single dict list-like
                    if all(isinstance(v, dict) for v in payload.values()):
                        projects = list(payload.values())
            return {
                "ok": True,
                "projects": projects,
                "attempts": attempts,
            }
    return {
        "ok": False,
        "projects": [],
        "attempts": attempts,
    }


def load_deployments_registry() -> Dict[str, Any]:
    path = REPO_ROOT / "dashboard" / ".runtime" / "studio" / "deployments.json"
    if not path.exists():
        return {"items": []}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {"items": []}
        if "items" not in data or not isinstance(data["items"], list):
            data["items"] = []
        return data
    except Exception:
        return {"items": []}


def classify_projects(projects: List[Dict[str, Any]], keep_prefix: str, used_projects: List[str]) -> Dict[str, Any]:
    used = {p for p in used_projects if p}
    keep: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    cleanup_candidates: List[Dict[str, Any]] = []

    keep_re = re.compile(rf"^{re.escape(keep_prefix)}", re.IGNORECASE)

    for proj in projects:
        if not isinstance(proj, dict):
            continue
        name = str(proj.get("name") or proj.get("id") or "").strip()
        if not name:
            continue

        rec = {
            "name": name,
            "id": proj.get("id"),
            "createdAt": proj.get("createdAt") or proj.get("created"),
            "updatedAt": proj.get("updatedAt") or proj.get("updated"),
            "framework": proj.get("framework"),
            "nodeVersion": proj.get("nodeVersion"),
            "usedByStudio": name in used,
            "matchesPrefix": bool(keep_re.search(name)),
        }

        if rec["usedByStudio"] or rec["matchesPrefix"]:
            keep.append(rec)
        elif any(tok in name.lower() for tok in ["tmp", "test", "demo", "project-", "web_product"]):
            cleanup_candidates.append(rec)
        else:
            review.append(rec)

    return {
        "keep": keep,
        "review": review,
        "cleanupCandidates": cleanup_candidates,
    }


def remove_project(name: str) -> Dict[str, Any]:
    cmd_variants = [
        ["vercel", "project", "rm", name, "--yes"],
        ["vercel", "projects", "rm", name, "--yes"],
    ]
    attempts = []
    for cmd in cmd_variants:
        result = run(cmd, timeout=120)
        attempts.append(result)
        if result.get("ok"):
            return {"ok": True, "name": name, "attempts": attempts}
    return {"ok": False, "name": name, "attempts": attempts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Vercel audit and conservative cleanup")
    parser.add_argument("--keep-prefix", default="op1-", help="project name prefix to keep (default: op1-)")
    parser.add_argument("--apply", action="store_true", help="apply cleanup candidates (destructive)")
    parser.add_argument("--strategy", choices=["archive", "delete"], default="archive", help="cleanup strategy when --apply is set")
    parser.add_argument("--max-delete", type=int, default=5, help="max candidates to delete per run")
    args = parser.parse_args()

    projects_info = vercel_projects_json()
    deployments = load_deployments_registry()
    used_projects = [str((item or {}).get("project") or "") for item in deployments.get("items", [])]

    classified = classify_projects(projects_info.get("projects", []), args.keep_prefix, used_projects)

    report = {
        "generatedAt": now_iso(),
        "ok": bool(projects_info.get("ok")),
        "keepPrefix": args.keep_prefix,
        "projectCount": len(projects_info.get("projects", [])),
        "usedProjectsCount": len({p for p in used_projects if p}),
        "classified": classified,
        "cleanup": {
            "apply": bool(args.apply),
            "strategy": args.strategy,
            "executed": [],
        },
        "attempts": projects_info.get("attempts", []),
    }

    if args.apply:
        candidates = classified.get("cleanupCandidates", [])[: max(0, args.max_delete)]
        for item in candidates:
            name = item.get("name")
            if not name:
                continue
            if args.strategy == "delete":
                result = remove_project(name)
                report["cleanup"]["executed"].append(result)
            else:
                report["cleanup"]["executed"].append(
                    {
                        "ok": True,
                        "name": name,
                        "action": "archive_todo",
                        "note": "archive strategy selected; please archive in Vercel dashboard after review",
                    }
                )

    out_path = RUNTIME_DIR / "vercel_audit.latest.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(str(out_path))


if __name__ == "__main__":
    main()
