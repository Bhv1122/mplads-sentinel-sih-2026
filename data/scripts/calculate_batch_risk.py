#!/usr/bin/env python3
"""
data/scripts/calculate_batch_risk.py
=============================================================================
CLI Runner for Batch Risk Calculation across MPLADS Dataset.
=============================================================================

Executes the complete 6-engine risk aggregation pipeline:
    Load project
    ↓
    Engine 1 — Cost Anomaly
    ↓
    Engine 2 — Duplicate Detection
    ↓
    Engine 3 — Delay Detection
    ↓
    Engine 4 — Financial/Physical Progress Mismatch
    ↓
    Engine 5 — Agency Pattern
    ↓
    Central Risk Aggregation
    ↓
    Engine 6 — Explanation
    ↓
    PostgreSQL

Usage Examples:
    # 1. Process all projects in database
    python data/scripts/calculate_batch_risk.py --all

    # 2. Process a single project
    python data/scripts/calculate_batch_risk.py --project MH-MUM-2023-001

    # 3. Process selected projects
    python data/scripts/calculate_batch_risk.py --projects MH-MUM-2023-001,DL-NDL-2023-002

    # 4. Dry run without persisting
    python data/scripts/calculate_batch_risk.py --all --no-persist

    # 5. Output JSON summary
    python data/scripts/calculate_batch_risk.py --all --json
"""

import sys
import json
import argparse
import logging
from pathlib import Path

# Add backend directory and project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from backend.app.services.risk.batch_risk_service import BatchRiskService, BatchRiskSummary


def setup_logging(verbose: bool = False, json_mode: bool = False):
    """Configures console logging directed to stderr to preserve stdout for JSON."""
    level = logging.DEBUG if verbose else (logging.WARNING if json_mode else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="MPLADS Batch Risk Calculation CLI Runner"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Calculate risk for all projects in the database.",
    )
    group.add_argument(
        "--project",
        type=str,
        help="Calculate risk for a single project by ID.",
    )
    group.add_argument(
        "--projects",
        type=str,
        help="Comma-separated list of project IDs to evaluate.",
    )

    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Dry run: evaluate risk without committing updates to PostgreSQL.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50,
        help="Batch commit chunk size (default: 50).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output execution summary as JSON instead of ASCII table.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed debug logging.",
    )

    return parser.parse_args()


def main():
    """CLI execution entrypoint."""
    args = parse_args()
    setup_logging(verbose=args.verbose, json_mode=args.json)

    service = BatchRiskService()
    persist = not args.no_persist

    try:
        from contextlib import redirect_stdout

        if args.project:
            # Single project execution
            if not args.json:
                print(f"\nEvaluating single project: '{args.project}' (persist={persist})...", file=sys.stderr)
            if args.json:
                with redirect_stdout(sys.stderr):
                    result = service.process_project(project_id=args.project, persist=persist)
                print(json.dumps(result, indent=2, default=str))
            else:
                result = service.process_project(project_id=args.project, persist=persist)
                score = result.get("overall_score", result.get("overall_risk_score", 0.0))
                tier = result.get("risk_level", "UNKNOWN")
                print("================================================================================")
                print(f"  Project ID           : {args.project}")
                print(f"  Overall Score        : {score:.2f} / 100")
                print(f"  Risk Tier            : {tier}")
                print(f"  Confidence           : {result.get('confidence', 0.0):.2f}")
                print(f"  Summary              : {result.get('summary', 'N/A')}")
                print("--------------------------------------------------------------------------------")
                print("  Engine Scores Breakdown:")
                for k, v in result.get("engine_scores", {}).items():
                    print(f"    - {k:22s}: {v:.2f}")
                print("================================================================================")
            sys.exit(0)

        elif args.projects:
            # Explicit list of projects
            pids = [p.strip() for p in args.projects.split(",") if p.strip()]
            if not args.json:
                print(f"\nEvaluating {len(pids)} selected projects (persist={persist})...\n", file=sys.stderr)
            if args.json:
                with redirect_stdout(sys.stderr):
                    summary = service.process_selected(
                        project_ids=pids,
                        persist=persist,
                        chunk_size=args.chunk_size,
                    )
            else:
                summary = service.process_selected(
                    project_ids=pids,
                    persist=persist,
                    chunk_size=args.chunk_size,
                )

        elif args.all:
            # All projects in database
            if not args.json:
                print(f"\nEvaluating ALL projects in database (persist={persist})...\n", file=sys.stderr)
            if args.json:
                with redirect_stdout(sys.stderr):
                    summary = service.process_all(
                        persist=persist,
                        chunk_size=args.chunk_size,
                    )
            else:
                summary = service.process_all(
                    persist=persist,
                    chunk_size=args.chunk_size,
                )

        # Output summary report
        if args.json:
            print(json.dumps(summary.to_dict(), indent=2))
        else:
            print("\n" + summary.format_ascii_report() + "\n")

        # Exit with 0 if no unhandled system errors
        sys.exit(0)

    except Exception as exc:
        logging.critical("Batch risk processing failed: %s", str(exc), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
