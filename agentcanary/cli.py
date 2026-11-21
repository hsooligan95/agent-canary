"""AgentCanary CLI.

    python -m agentcanary compare --base v1 --candidate v2-bad [--out reports/x.md]
    python -m agentcanary baseline --version v1 [--out baselines/v1.baseline.json]
    python -m agentcanary drift [--version v1] [--baseline baselines/v1.baseline.json]

Exit codes are the CI contract: 0 = PROMOTE / no drift,
2 = BLOCK, 3 = drift detected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .report import render_compare, render_drift
from .runner import load_thresholds, run_version
from .scoring import compare_runs, drift_check

_ROOT = Path(__file__).parent.parent


def _write(path: str | None, text: str) -> None:
    if path:
        out = _ROOT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)


def cmd_compare(args: argparse.Namespace) -> int:
    thresholds = load_thresholds()
    base = run_version(args.base)
    candidate = run_version(args.candidate)
    diff = compare_runs(base, candidate, thresholds)
    report = render_compare(diff, thresholds)
    print(report)
    default_out = f"reports/compare-{args.base}-vs-{args.candidate}.md"
    _write(args.out if args.out is not None else default_out, report)
    return 0 if diff["decision"] == "PROMOTE" else 2


def cmd_baseline(args: argparse.Namespace) -> int:
    result = run_version(args.version)
    out = _ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"baseline for {args.version} written to {out}", file=sys.stderr)
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    baseline_path = _ROOT / args.baseline
    if not baseline_path.exists():
        print(f"no baseline at {baseline_path}; run the baseline command first",
              file=sys.stderr)
        return 1
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = run_version(args.version)
    drift = drift_check(baseline, current, load_thresholds())
    report = render_drift(drift)
    print(report)
    _write(f"reports/drift-{args.version}.md", report)
    return 3 if drift["drift_detected"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentcanary", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("compare", help="compare two agent versions over the golden suite")
    p.add_argument("--base", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", default=None, help="report path (default reports/compare-*.md)")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("baseline", help="record a version's suite results as the drift baseline")
    p.add_argument("--version", required=True)
    p.add_argument("--out", default="baselines/v1.baseline.json")
    p.set_defaults(fn=cmd_baseline)

    p = sub.add_parser("drift", help="re-run the pinned version and diff against its baseline")
    p.add_argument("--version", default="v1")
    p.add_argument("--baseline", default="baselines/v1.baseline.json")
    p.set_defaults(fn=cmd_drift)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
