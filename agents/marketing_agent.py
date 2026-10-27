"""Deterministic, explainable next-day budget recommendations (no LLM needed)."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Mapping

import numpy as np
import pandas as pd

from analysis.performance import calculate_performance

CHANNELS = ("Search", "Social", "Display")
DAILY_BUDGET = 300.0
MIN_BUDGET = 30.0
MAX_CHANGE = 0.20
RECENT_DAYS = 7


@dataclass
class OptimizationResult:
    historical: pd.DataFrame
    recent: pd.DataFrame
    channel_summary: pd.DataFrame
    decision_log: pd.DataFrame
    guardrails: dict[str, bool]
    recent_start: str
    observed_through: str


def _current_allocation(frame: pd.DataFrame, dates: pd.Series,
                        supplied: Mapping[str, float] | None) -> pd.Series:
    """Use actual latest-day spending unless the caller supplies current budgets."""
    if supplied is None:
        latest = frame.loc[dates.eq(dates.max()), ["channel", "spend"]].copy()
        # Sum decimal currency before converting to floats so campaign totals
        # such as $0.02 + $99.99 remain exactly $100.01 during validation.
        latest["spend"] = latest["spend"].map(lambda value: Decimal(str(value)))
        supplied = latest.groupby("channel")["spend"].sum().to_dict()
    if set(supplied) != set(CHANNELS):
        raise ValueError("Current budgets must include exactly Search, Social, and Display")
    amounts = pd.Series(supplied, dtype=float).reindex(CHANNELS)
    if not np.isfinite(amounts).all() or amounts.le(0).any():
        raise ValueError("Current budgets must be finite and positive")
    cents = [Decimal(str(value)) * 100 for value in amounts]
    if any(value != value.to_integral_value() for value in cents):
        raise ValueError("Current budgets must be in whole cents")
    if sum(cents) != Decimal("30000"):
        raise ValueError("Current budgets must total $300; supply current_budgets explicitly if needed")
    return amounts


def score_channels(historical: pd.DataFrame, recent: pd.DataFrame) -> pd.DataFrame:
    """Score = 75% relative conversions/$ + 25% relative CVR.

    Each input blends 50% lifetime and 50% latest seven calendar days, then
    divides by the best channel's blended value. Thus scores are in [0, 1].
    Conversions/$ is inverse CPA, so CPA is not counted a second time.
    CTR and raw conversion counts are reported as context, not click rewards.
    A channel absent from the recent window falls back to its history.
    """
    history = historical.reindex(CHANNELS)
    latest = recent.reindex(CHANNELS)
    historical_efficiency = (history.conversions / history.spend.replace(0, np.nan)).fillna(0)
    recent_efficiency = latest.conversions / latest.spend.replace(0, np.nan)
    recent_efficiency = recent_efficiency.fillna(historical_efficiency)
    blended_efficiency = (historical_efficiency + recent_efficiency) / 2
    blended_cvr = (history.CVR.fillna(0) + latest.CVR.fillna(history.CVR).fillna(0)) / 2
    relative_efficiency = blended_efficiency / (blended_efficiency.max() or 1)
    relative_cvr = blended_cvr / (blended_cvr.max() or 1)
    return pd.DataFrame({
        "historical_conversions_per_dollar": historical_efficiency,
        "recent_conversions_per_dollar": recent_efficiency,
        "blended_conversions_per_dollar": blended_efficiency,
        "blended_CVR": blended_cvr,
        "optimization_score": 0.75 * relative_efficiency + 0.25 * relative_cvr,
    })


def allocate_budget(scores: pd.Series, previous: pd.Series) -> pd.Series:
    """Fit score-proportional targets within exploration and daily-change bounds.

    Reserve $30/channel; target the remaining $210 proportionally to score.
    Find a common multiplier for these targets so clipping to the bounds
    still totals $300. A binary search works because a larger multiplier
    can only increase the total. Round inside the bounds in whole cents.
    """
    lower = np.array([int(max(Decimal("3000"), Decimal(str(v)) * 80)
                          .to_integral_value(rounding=ROUND_CEILING)) for v in previous])
    upper = np.array([int((Decimal(str(v)) * 120)
                          .to_integral_value(rounding=ROUND_FLOOR)) for v in previous])
    if (lower > upper).any() or lower.sum() > 30000 or upper.sum() < 30000:
        raise ValueError("No feasible $300 allocation satisfies both exploration and +/-20% limits")
    if scores.sum() == 0:
        # With no conversion evidence, keep a valid existing allocation.
        targets = previous.to_numpy() * 100
    else:
        targets = (MIN_BUDGET + 210 * scores / scores.sum()).to_numpy() * 100
    low, high = 0.0, max(upper / targets) + 1
    for _ in range(80):
        multiplier = (low + high) / 2
        if np.clip(targets * multiplier, lower, upper).sum() < 30000:
            low = multiplier
        else:
            high = multiplier
    fitted = np.clip(targets * high, lower, upper)
    cents = np.floor(fitted).astype(int)
    # Largest fractional remainders get leftover cents; channel order breaks ties.
    order = np.argsort(-(fitted - cents), kind="stable")
    for index in order:
        if cents.sum() == 30000:
            break
        if cents[index] < upper[index]:
            cents[index] += 1
    return pd.Series(cents / 100, index=previous.index, name="recommended_budget")


def check_guardrails(previous: pd.Series, recommended: pd.Series) -> dict[str, bool]:
    """Check the final, rounded allocations rather than unrounded targets."""
    return {
        "Fixed $300 daily budget": sum(round(v * 100) for v in recommended) == 30000,
        "Every channel receives a positive budget": bool(recommended.gt(0).all()),
        "At least $30 (10%) per channel": bool(recommended.ge(MIN_BUDGET).all()),
        "Daily changes within +/-20%": bool(
            ((recommended - previous).abs() <= previous * MAX_CHANGE + 1e-9).all()
        ),
    }


def _rate(value: float, money: bool = False) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${value:.2f}" if money else f"{value:.2%}"


def _explain(row: pd.Series, no_evidence: bool) -> str:
    movement = "increased" if row.change_amount > 0 else "decreased" if row.change_amount < 0 else "remained stable"
    evidence = (
        f"Budget {movement}; score {row.optimization_score:.3f}. "
        f"Historical CVR {_rate(row.CVR)}, CPA {_rate(row.CPA, True)}; "
        f"recent CVR {_rate(row.recent_CVR)}, CPA {_rate(row.recent_CPA, True)}. "
    )
    if no_evidence:
        evidence += "No usable conversion evidence; retain current budgets where feasible. "
    elif pd.isna(row.recent_spend):
        evidence += "No observations in the recent window; using historical evidence. "
    else:
        evidence += (
            f"Conversions per $100: historical {row.historical_conversions_per_dollar * 100:.2f}, "
            f"recent {row.recent_conversions_per_dollar * 100:.2f}. "
        )
    return evidence + "Score-based target adjusted to keep $300 total, $30 exploration and +/-20% changes."


def optimize_budget(frame: pd.DataFrame,
                    current_budgets: Mapping[str, float] | None = None) -> OptimizationResult:
    """Observe -> calculate -> score -> constrain -> explain; never mutate input.

    Re-run with new observations and the actual current allocation to continue
    the lightweight learning loop. No ad-platform budgets are changed here.
    """
    historical = calculate_performance(frame)
    if set(frame.channel) != set(CHANNELS):
        raise ValueError("Data must contain exactly Search, Social, and Display")
    dates = pd.to_datetime(frame.date, format="ISO8601").dt.normalize()
    end = dates.max()
    start = end - pd.Timedelta(days=RECENT_DAYS - 1)
    recent = calculate_performance(frame.loc[dates.ge(start)])
    previous = _current_allocation(frame, dates, current_budgets)
    scores = score_channels(historical, recent)
    recommended = allocate_budget(scores.optimization_score, previous)
    guardrails = check_guardrails(previous, recommended)
    if not all(guardrails.values()):
        raise ValueError(f"Final allocation failed guardrails: {guardrails}")
    summary = historical.reindex(CHANNELS).join(recent.drop(index="Total").add_prefix("recent_"))
    summary = summary.join(scores)
    summary["previous_budget"] = previous
    summary["recommended_budget"] = recommended
    summary["change_amount"] = recommended - previous
    summary["change_pct"] = summary.change_amount / previous
    summary["date"] = (end + pd.Timedelta(days=1)).date().isoformat()
    summary["reason"] = summary.apply(
        _explain, axis=1, no_evidence=bool(scores.optimization_score.eq(0).all())
    )
    summary.index.name = "channel"
    decision_columns = ["date", "channel", "previous_budget", "recommended_budget",
                        "change_amount", "change_pct", "CTR", "CVR", "CPA",
                        "recent_CTR", "recent_CVR", "recent_CPA", "optimization_score", "reason"]
    log = summary.reset_index()[decision_columns]
    return OptimizationResult(historical, recent, summary, log, guardrails,
                              start.date().isoformat(), end.date().isoformat())
