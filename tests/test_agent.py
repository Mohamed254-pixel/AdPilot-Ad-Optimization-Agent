"""Behavioral checks for scoring, budgets, explanations, and the terminal report."""

from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from agents.marketing_agent import CHANNELS, optimize_budget
from analysis.performance import COLUMNS, calculate_performance
from data.generate_data import generate_data
from evaluation.evaluate import evaluate_allocation


def assert_valid_budgets(result):
    plan = result.channel_summary
    assert sum(Decimal(str(v)) for v in plan.recommended_budget) == Decimal("300")
    assert plan.recommended_budget.ge(30).all()
    assert plan.recommended_budget.gt(0).all()
    assert ((plan.recommended_budget - plan.previous_budget).abs()
            <= plan.previous_budget * .20 + 1e-9).all()
    assert all(result.guardrails.values())


def test_sample_recommendation_and_reasons():
    frame = generate_data()
    original = frame.copy(deep=True)
    result = optimize_budget(frame)
    assert_valid_budgets(result)
    plan = result.channel_summary
    assert plan.loc["Search", "recommended_budget"] > 100
    assert plan.loc["Display", "recommended_budget"] < 100
    assert result.decision_log.date.eq("2026-01-31").all()
    assert result.decision_log.reason.str.len().gt(50).all()
    assert plan.loc["Search", "reason"].startswith("Budget increased")
    assert "decreased" in plan.loc["Display", "reason"]
    assert result.recent_start == "2026-01-24"
    assert result.recent.loc["Total", "spend"] == 2100
    pd.testing.assert_frame_equal(result.historical, calculate_performance(frame))
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_frame_equal(result.decision_log, optimize_budget(frame).decision_log)


def test_winner_is_data_driven_not_channel_name_or_click_count():
    frame = generate_data()
    frame["channel"] = frame.channel.replace({"Search": "Display", "Display": "Search"})
    result = optimize_budget(frame)
    assert result.channel_summary.recommended_budget.idxmax() == "Display"
    # All channels get equal clicks, but Social has the most conversions.
    rows = [["2026-01-01", ch, 100, 10000, 500, conv]
            for ch, conv in zip(CHANNELS, [1, 40, 2])]
    result = optimize_budget(pd.DataFrame(rows, columns=COLUMNS))
    assert result.channel_summary.recommended_budget.idxmax() == "Social"


@pytest.mark.parametrize("zero_clicks", [False, True])
def test_zero_conversions_are_safe_and_preserve_current_budgets(zero_clicks):
    frame = generate_data()
    frame["conversions"] = 0
    if zero_clicks:
        frame[["clicks", "impressions"]] = 0
    current = {"Search": 120, "Social": 100, "Display": 80}
    result = optimize_budget(frame, current)
    assert_valid_budgets(result)
    assert result.channel_summary.optimization_score.eq(0).all()
    assert result.channel_summary.CPA.isna().all()
    assert result.channel_summary.recommended_budget.to_dict() == current
    assert result.decision_log.reason.str.contains("No usable conversion evidence").all()
    comparison = evaluate_allocation(result)
    assert comparison.estimated_conversions.eq(0).all()
    assert comparison.estimated_CPA.isna().all()
    assert comparison.conversion_lift.isna().all()


def test_one_zero_conversion_channel_keeps_exploration():
    frame = generate_data()
    frame.loc[frame.channel.eq("Display"), "conversions"] = 0
    result = optimize_budget(frame)
    assert_valid_budgets(result)
    assert result.channel_summary.loc["Display", "optimization_score"] == 0
    assert "CPA N/A" in result.channel_summary.loc["Display", "reason"]


def test_recent_reversal_changes_ranking():
    rows = []
    for day in range(1, 31):
        for channel in CHANNELS:
            conversions = {"Search": 24, "Social": 10, "Display": 2}[channel]
            if day >= 24:
                conversions = {"Search": 1, "Social": 40, "Display": 2}[channel]
            rows.append([f"2026-01-{day:02d}", channel, 100, 10000, 500, conversions])
    result = optimize_budget(pd.DataFrame(rows, columns=COLUMNS))
    assert result.historical.loc["Search", "conversions"] > result.historical.loc["Social", "conversions"]
    assert result.channel_summary.optimization_score.idxmax() == "Social"
    assert result.channel_summary.recommended_budget.idxmax() == "Social"


def test_missing_recent_channel_falls_back_to_history():
    frame = generate_data()
    frame = frame[~(frame.channel.eq("Display") & frame.date.ge("2026-01-24"))]
    result = optimize_budget(frame, dict.fromkeys(CHANNELS, 100))
    assert_valid_budgets(result)
    assert result.channel_summary.optimization_score.notna().all()
    assert "No observations in the recent window" in result.channel_summary.loc["Display", "reason"]


def test_latest_day_budget_is_inferred_and_explicit_budget_can_override():
    frame = generate_data()
    for channel, budget in {"Search": 120, "Social": 100, "Display": 80}.items():
        frame.loc[frame.date.eq("2026-01-30") & frame.channel.eq(channel), "spend"] = budget
    inferred = optimize_budget(frame)
    assert inferred.channel_summary.previous_budget.to_dict() == {"Search": 120, "Social": 100, "Display": 80}
    assert_valid_budgets(inferred)
    overridden = optimize_budget(frame, dict.fromkeys(CHANNELS, 100))
    assert overridden.channel_summary.previous_budget.eq(100).all()


@pytest.mark.parametrize("current", [
    {"Search": 150, "Social": 100, "Display": 50},
    {"Search": 240, "Social": 30, "Display": 30},
    {"Search": 33.33, "Social": 133.33, "Display": 133.34},
    {"Search": 25, "Social": 100, "Display": 175},
    {"Search": 100.01, "Social": 99.99, "Display": 100},
])
def test_feasible_non_equal_allocations_and_rounding(current):
    assert_valid_budgets(optimize_budget(generate_data(), current))


@pytest.mark.parametrize("current, message", [
    ({"Search": 10, "Social": 145, "Display": 145}, "No feasible"),
    ({"Search": 100, "Social": 100, "Display": 90}, "total"),
    ({"Search": 100, "Social": 200}, "exactly"),
    ({"Search": float("nan"), "Social": 100, "Display": 100}, "finite"),
    ({"Search": 0, "Social": 150, "Display": 150}, "positive"),
    ({"Search": 100.001, "Social": 99.999, "Display": 100}, "whole cents"),
])
def test_invalid_or_infeasible_current_allocations_are_rejected(current, message):
    with pytest.raises(ValueError, match=message):
        optimize_budget(generate_data(), current)


def test_incomplete_latest_day_and_unsupported_channels_are_rejected():
    frame = generate_data()
    with pytest.raises(ValueError, match="exactly"):
        optimize_budget(frame[~(frame.date.eq("2026-01-30") & frame.channel.eq("Display"))])
    with pytest.raises(ValueError, match="exactly"):
        optimize_budget(frame.replace({"channel": {"Display": "Other"}}))


def test_score_matches_documented_formula():
    result = optimize_budget(generate_data())
    plan = result.channel_summary
    efficiency = (plan.conversions / plan.spend + plan.recent_conversions / plan.recent_spend) / 2
    cvr = (plan.CVR + plan.recent_CVR) / 2
    expected = .75 * efficiency / efficiency.max() + .25 * cvr / cvr.max()
    np.testing.assert_allclose(plan.optimization_score, expected)


def test_equal_performance_produces_stable_equal_budgets():
    frame = pd.DataFrame([["2026-01-01", ch, 100, 1000, 100, 10] for ch in CHANNELS], columns=COLUMNS)
    result = optimize_budget(frame)
    assert result.channel_summary.recommended_budget.eq(100).all()
    assert result.decision_log.reason.str.contains("remained stable").all()


def test_zero_spend_and_short_history_are_safe():
    frame = generate_data().iloc[:6].copy()
    frame["spend"] = 0.0
    result = optimize_budget(frame, dict.fromkeys(CHANNELS, 100))
    assert_valid_budgets(result)
    assert np.isfinite(result.channel_summary.optimization_score).all()
    assert evaluate_allocation(result).estimated_conversions.eq(0).all()


def test_evaluation_uses_same_rates_for_both_allocations():
    result = optimize_budget(generate_data())
    comparison = evaluate_allocation(result)
    expected_baseline = result.historical.loc["Total", "conversions"] / 30
    expected_agent = sum(result.channel_summary.recommended_budget
                         * result.channel_summary.conversions / result.channel_summary.spend)
    assert comparison.loc["Baseline", "estimated_conversions"] == pytest.approx(expected_baseline)
    assert comparison.loc["Agent", "estimated_conversions"] == pytest.approx(expected_agent)
    assert comparison.loc["Agent", "estimated_CPA"] == pytest.approx(300 / expected_agent)
    assert comparison.loc["Agent", "conversion_lift"] == pytest.approx(expected_agent / expected_baseline - 1)


def test_cli_runs_from_another_directory(tmp_path):
    main = Path(__file__).resolve().parents[1] / "main.py"
    completed = subprocess.run([sys.executable, str(main)],
                               cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "ADPILOT" in completed.stdout
    assert "Total recommended: $300.00" in completed.stdout
    assert completed.stdout.count("PASS |") == 4
    assert "not real future conversions" in completed.stdout
    assert "HISTORICAL CHANNEL PERFORMANCE" in completed.stdout
    assert "RECENT PERFORMANCE" in completed.stdout
    assert "AGENT RATIONALE" in completed.stdout
    assert "ILLUSTRATIVE BASELINE VS AGENT" in completed.stdout
    assert "27.77" in completed.stdout
    assert "30.83" in completed.stdout
    assert "11.02%" in completed.stdout
    assert list(tmp_path.iterdir()) == []
