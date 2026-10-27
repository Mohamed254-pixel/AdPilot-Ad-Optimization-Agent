"""Run AdPilot and print performance, budget decisions, and estimated evaluation."""

import argparse
from pathlib import Path
import textwrap

import pandas as pd

from agents.marketing_agent import OptimizationResult, optimize_budget
from analysis.performance import DEFAULT_INPUT
from evaluation.evaluate import ASSUMPTIONS, evaluate_allocation


def print_report(result: OptimizationResult) -> None:
    money = lambda value: f"${value:,.2f}"
    percent = lambda value: f"{value:.2%}"
    formatters = {"spend": money, "CTR": percent, "CVR": percent, "CPA": money}
    print("=" * 78)
    print("ADPILOT | Marketing Ad Optimization Agent")
    print(f"Observed through {result.observed_through} | Next-day plan: {result.decision_log.date.iloc[0]}")
    print("Goal: more conversions within a fixed $300 daily budget")
    print("=" * 78)
    columns = ["spend", "conversions", "CTR", "CVR", "CPA"]
    print("\nHISTORICAL CHANNEL PERFORMANCE")
    print(result.historical[columns].to_string(formatters=formatters, na_rep="N/A"))
    print(f"\nRECENT PERFORMANCE | {result.recent_start} to {result.observed_through}")
    print(result.recent[columns].to_string(formatters=formatters, na_rep="N/A"))
    print("\nNEXT-DAY BUDGET | Current allocation comes from the latest observed day")
    allocation = result.channel_summary[["optimization_score", "previous_budget", "recommended_budget",
                                         "change_amount", "change_pct"]].rename(columns={
        "optimization_score": "Score", "previous_budget": "Current", "recommended_budget": "Recommended",
        "change_amount": "Change", "change_pct": "Change %"})
    print(allocation.to_string(formatters={"Score": "{:.3f}".format, "Current": money,
        "Recommended": money, "Change": lambda v: f"{v:+.2f}", "Change %": lambda v: f"{v:+.2%}"}))
    print(f"Total recommended: ${result.channel_summary.recommended_budget.sum():.2f}")
    print("Score: 75% relative conversions/$ + 25% relative CVR; each blends 50% history / 50% recent.")
    print("\nAGENT RATIONALE")
    for channel, row in result.channel_summary.iterrows():
        print(textwrap.fill(f"{channel}: {row.reason}", width=78,
                            initial_indent="  ", subsequent_indent="    "))
    print("\nILLUSTRATIVE BASELINE VS AGENT | Full-history conversion rates")
    comparison = evaluate_allocation(result)
    print(comparison[["daily_budget", "estimated_conversions", "estimated_CPA", "conversion_lift"]]
          .to_string(formatters={"daily_budget": money, "estimated_conversions": "{:.2f}".format,
                                 "estimated_CPA": money, "conversion_lift": percent}, na_rep="N/A"))
    print(textwrap.fill(ASSUMPTIONS, width=78))
    print("\nGUARDRAILS")
    for rule, passed in result.guardrails.items():
        print(f"  {'PASS' if passed else 'FAIL'} | {rule}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        frame = pd.read_csv(args.input)
        result = optimize_budget(frame)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print_report(result)


if __name__ == "__main__":
    main()
