"""Illustrative counterfactual estimates, not measured future performance."""

import pandas as pd

from agents.marketing_agent import CHANNELS, OptimizationResult

ASSUMPTIONS = (
    "Illustrative estimates only, not real future conversions or a causal test. "
    "Assume each channel's historical conversions per dollar stays constant "
    "as budget changes (linear response; no saturation, auction or cross-channel effects). "
    "Both allocations use the same full-history rates; evaluation reuses training data. "
    "A zero-spend channel has no measurable rate and is estimated at zero conversions."
)


def evaluate_allocation(result: OptimizationResult) -> pd.DataFrame:
    """Compare equal $100 budgets and the agent using identical historical rates."""
    rates = result.channel_summary.historical_conversions_per_dollar
    rows = []
    for label, budgets in (
        ("Baseline", pd.Series(100.0, index=CHANNELS)),
        ("Agent", result.channel_summary.recommended_budget),
    ):
        conversions = float((budgets * rates).sum())
        rows.append({
            "strategy": label,
            "daily_budget": float(budgets.sum()),
            "estimated_conversions": conversions,
            "estimated_CPA": float(budgets.sum()) / conversions if conversions else float("nan"),
            **{f"{channel.lower()}_budget": float(budgets[channel]) for channel in CHANNELS},
        })
    comparison = pd.DataFrame(rows).set_index("strategy")
    baseline = comparison.loc["Baseline", "estimated_conversions"]
    comparison["conversion_lift"] = (
        comparison.estimated_conversions / baseline - 1 if baseline else float("nan")
    )
    return comparison
