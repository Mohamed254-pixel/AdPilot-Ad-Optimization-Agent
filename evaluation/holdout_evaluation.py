"""Evaluate a fixed allocation on nine unseen days of mock data."""

from pathlib import Path

import pandas as pd

from agents.marketing_agent import CHANNELS, optimize_budget


def main():
    root = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(root / "data" / "ad_performance.csv")

    dates = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    unique_dates = sorted(dates.unique())

    if len(unique_dates) != 30:
        raise ValueError("This evaluation expects exactly 30 dates.")

    train_dates = unique_dates[:21]
    test_dates = unique_dates[21:]

    training = frame.loc[dates.isin(train_dates)].copy()
    testing = frame.loc[dates.isin(test_dates)].copy()

    # Only the first 21 days are supplied to the agent.
    result = optimize_budget(
        training,
        current_budgets=dict.fromkeys(CHANNELS, 100.0),
    )

    if not all(result.guardrails.values()):
        raise ValueError("The recommended allocation failed a guardrail.")

    baseline = pd.Series(100.0, index=CHANNELS)
    agent = result.channel_summary["recommended_budget"].reindex(CHANNELS)

    daily_rows = []

    for day in test_dates:
        observed = testing.loc[
            dates.loc[testing.index].eq(day)
        ]
        totals = observed.groupby("channel")[
            ["spend", "conversions"]
        ].sum().reindex(CHANNELS)

        if totals.isna().any().any() or totals["spend"].le(0).any():
            raise ValueError(
                "Every test day must have positive spend for all channels."
            )

        # Test-day rates score the frozen plan; they never choose its budgets.
        rates = totals["conversions"] / totals["spend"]

        for strategy, budgets in (
            ("Baseline", baseline),
            ("Agent", agent),
        ):
            daily_rows.append({
                "date": pd.Timestamp(day).date().isoformat(),
                "strategy": strategy,
                "spend": float(budgets.sum()),
                "estimated_conversions": float((budgets * rates).sum()),
            })

    daily = pd.DataFrame(daily_rows)

    summary = daily.groupby("strategy", sort=False)[
        ["spend", "estimated_conversions"]
    ].sum()

    summary["estimated_CPA"] = (
        summary["spend"]
        / summary["estimated_conversions"].replace(0, float("nan"))
    )

    baseline_conversions = summary.loc[
        "Baseline", "estimated_conversions"
    ]
    summary["conversion_lift_pct"] = (
        (summary["estimated_conversions"] / baseline_conversions - 1) * 100
        if baseline_conversions > 0
        else float("nan")
    )

    print("HOLDOUT EVALUATION")
    print(
        f"Training: {pd.Timestamp(train_dates[0]).date()} "
        f"through {pd.Timestamp(train_dates[-1]).date()}"
    )
    print(
        f"Testing:  {pd.Timestamp(test_dates[0]).date()} "
        f"through {pd.Timestamp(test_dates[-1]).date()}"
    )
    print("\nDaily budgets held fixed throughout testing:")
    print(pd.DataFrame({"Baseline": baseline, "Agent": agent}).to_string())
    print("\nResults over all nine test days:")
    print(summary.to_string(float_format=lambda value: f"{value:.2f}"))

    print("\nGuardrails for the initial budget change:")
    for name, passed in result.guardrails.items():
        print(f"{'PASS' if passed else 'FAIL'} | {name}")

    print(
        "\nSimulated estimates using unseen mock-data days. "
        "Assumes conversions scale linearly with spend, with no saturation "
        "or cross-channel effects. This is not measured advertising lift."
    )

    daily.to_csv(root / "evaluation" / "holdout_daily_results.csv", index=False)
    summary.to_csv(root / "evaluation" / "holdout_summary.csv")
    print("\nSaved holdout_daily_results.csv and holdout_summary.csv.")


if __name__ == "__main__":
    main()