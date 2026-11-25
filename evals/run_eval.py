"""Extraction scorecard against the synthetic fixtures.

    make eval        live model; costs money, ask the owner first
    make eval-fake   no outside call: replays each fixture's expected output through
                     the pipeline, which checks the pipeline and the scorecard, not the model

Each run appends a line to evals/history.jsonl so regressions are visible.
"""

import argparse
import sys

from atlas.evaluation.fixtures import fixture_names
from atlas.evaluation.runner import run_eval
from atlas.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--providers", choices=["live", "oracle"], default="live")
    parser.add_argument("--fixture", action="append", help="fixture name; repeat for several")
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    live = args.providers == "live"
    if live:
        settings = settings.model_copy(update={"providers": "live"})
    names = args.fixture or fixture_names()
    kwargs = {"history": None} if args.no_history else {}
    outcome = run_eval(settings, names, live=live, **kwargs)  # type: ignore[arg-type]

    sys.stdout.write(f"Fixtures: {', '.join(names)}  ({args.providers})\n\n{outcome.scorecard}\n")
    if outcome.failed:
        sys.stdout.write(f"\nDid not finish: {', '.join(outcome.failed)}\n")
    if outcome.usage:
        tokens = ", ".join(f"{k}={v}" for k, v in sorted(outcome.usage.items()))
        sys.stdout.write(f"\nTokens: {tokens}\n")
    if not live:
        sys.stdout.write(
            "\nOracle run: this checks the pipeline and scorecard, not extraction quality.\n"
        )
    return 0 if outcome.all_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
