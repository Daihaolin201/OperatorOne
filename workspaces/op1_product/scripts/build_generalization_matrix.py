#!/usr/bin/env python3
"""Build generalized validation matrix for modular web-product runs."""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import pathlib
from typing import Any, Dict, List


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def jaccard(a: List[str], b: List[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build modular generalization matrix")
    parser.add_argument("--base-dir", required=True, help="Base artifact directory containing adapter subdirs")
    parser.add_argument("--out", required=True, help="Output matrix JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = pathlib.Path(args.base_dir).resolve()
    out_path = pathlib.Path(args.out).resolve()

    if not base_dir.exists():
        raise FileNotFoundError(f"Base dir not found: {base_dir}")

    rows: List[Dict[str, Any]] = []

    for adapter_dir in sorted([p for p in base_dir.iterdir() if p.is_dir()]):
        deploy = read_json(adapter_dir / "deploy_latest.json")
        smoke = read_json(adapter_dir / "smoke_test.latest.json")
        business = read_json(adapter_dir / "business_test.latest.json")
        page_strategy = read_json(adapter_dir / "page_strategy.latest.json")

        page_specs = sorted(adapter_dir.glob("page_spec_*.json"))
        if not page_specs:
            raise FileNotFoundError(f"No page_spec_*.json found in {adapter_dir}")
        latest_page_spec = page_specs[-1]
        page_spec = read_json(latest_page_spec)

        modules = [
            str(m.get("module_id"))
            for m in page_spec.get("modules", [])
            if isinstance(m, dict) and m.get("module_id")
        ]

        rows.append(
            {
                "adapter_key": adapter_dir.name,
                "project_id": page_spec.get("project_id"),
                "adapter_name": page_spec.get("adapter_name"),
                "layout_profile": page_spec.get("layout_profile"),
                "deployed_url": deploy.get("public_url") or deploy.get("deployment_url"),
                "status": {
                    "smoke": smoke.get("status"),
                    "page_strategy": page_strategy.get("status"),
                    "business": business.get("status"),
                    "overall": "passed"
                    if smoke.get("status") == "passed"
                    and page_strategy.get("status") == "passed"
                    and business.get("status") == "passed"
                    else "failed",
                },
                "module_order": modules,
                "module_count": len(modules),
                "artifacts": {
                    "dir": str(adapter_dir),
                    "page_spec": str(latest_page_spec),
                    "smoke": str(adapter_dir / "smoke_test.latest.json"),
                    "page_strategy": str(adapter_dir / "page_strategy.latest.json"),
                    "business": str(adapter_dir / "business_test.latest.json"),
                },
            }
        )

    comparisons: List[Dict[str, Any]] = []
    for a, b in itertools.combinations(rows, 2):
        a_modules = a.get("module_order", [])
        b_modules = b.get("module_order", [])

        same_order = a_modules == b_modules
        overlap = jaccard(a_modules, b_modules)

        comparisons.append(
            {
                "pair": [a.get("adapter_name"), b.get("adapter_name")],
                "same_order": same_order,
                "jaccard_module_overlap": round(overlap, 3),
                "symmetric_difference": sorted(list(set(a_modules) ^ set(b_modules))),
            }
        )

    summary = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "base_dir": str(base_dir),
        "project_count": len(rows),
        "all_passed": all(r.get("status", {}).get("overall") == "passed" for r in rows),
        "projects": rows,
        "pairwise_structure_comparisons": comparisons,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out_path), "project_count": len(rows), "all_passed": summary["all_passed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
