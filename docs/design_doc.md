# AdPilot core design

AdPilot is a deterministic decision-support prototype. It recommends next-day
channel budgets; it does not send changes to an advertising platform.

## Existing foundation

`data/generate_data.py` produces reproducible aggregate mock advertising data.
`analysis/performance.py` validates it, aggregates counts, and calculates weighted
CTR (clicks/impressions), CVR (conversions/clicks), and CPA (spend/conversions).
The agent calls this existing module rather than duplicating metric calculations.

## Observe, score, allocate, explain

`agents/marketing_agent.py::optimize_budget` accepts a DataFrame and optional
actual current budgets. All three channels must be present. Without an explicit
allocation, latest-day spend is used; missing channels on that day or totals
other than $300 require the caller to supply a complete current allocation.
The input DataFrame is never modified.

The recent window includes the latest date and preceding six calendar days.
Counts are aggregated before calculating ratios. For each channel:

```
efficiency = 0.5 * historical_conversions_per_dollar
           + 0.5 * recent_conversions_per_dollar
response = 0.5 * historical_CVR + 0.5 * recent_CVR
score = 0.75 * efficiency / max_channel_efficiency
      + 0.25 * response / max_channel_response
target_budget = 30 + 210 * score / sum_channel_scores
```

An all-zero component contributes zero. Missing recent rates fall back to the
corresponding historical rate. Missing historical rates contribute zero; a
zero-spend channel has no measurable conversions-per-dollar rate. A recent
positive-spend period with zero conversions contributes zero efficiency. Undefined
CPA stays undefined, avoiding division-by-zero and false zero-cost claims.
CTR and raw conversions appear in reports but do not drive click maximization.
CPA efficiency is already represented by conversions per dollar, its reciprocal.
The fixed weights prioritize efficiency and are explained policy choices.

Exploration is the $30 minimum per channel; exploitation is the score-proportional
target for the remaining $210. For each channel, the feasible interval is:

```
lower = max($30, 80% of current budget), rounded up to a cent
upper = 120% of current budget, rounded down to a cent
```

The allocator searches for a common multiplier on target budgets, clips each
scaled target into its interval, and finds a $300 total. This is a monotone
search, not a machine-learning model. It rounds down to cents and distributes
leftover cents by fractional remainder, with fixed channel order for ties.
The final rounded budgets are checked again. Impossible combinations (for
example, a $10 current budget cannot reach the $30 floor in one 20% step) raise
an error. With all-zero scores, valid current budgets are retained; if a floor
requires adjustment, the same bounded fitting procedure applies.

Each channel gets a dated decision with prior and recommended budget, dollar
and percentage change, historical and recent rates, score, and a plain-language
reason. `OptimizationResult` holds the summaries, decision log and guardrail
checks. The terminal report displays performance, recommendations, and reasons.
The documentation prompt describes this policy; it is not executed by an LLM.

## Lightweight learning loop and evaluation

New observed results are added to the input data, then the agent is run again
with the actual current allocation. Recent evidence updates scores; no model
training, random exploration, hidden state or API dependency is needed.
Re-running unchanged inputs gives identical results. A run prints a report
without simulating future performance or building persistent history.

Evaluation estimates conversions by multiplying each budget by that channel's
full-history conversions per dollar. Both baseline and agent use identical rates.
Estimated CPA is $300 divided by estimated conversions; lift is the agent estimate
divided by the baseline estimate minus one. With no estimated conversions CPA
and lift are undefined. This in-sample, linear counterfactual cannot establish
causal improvement. It ignores saturation, auction changes, attribution delay,
cross-channel effects, and uncertainty in small samples. Recent observations
overlap the historical sample intentionally, emphasizing recent behavior.

The score allocation is a simple heuristic, not a proof of globally maximum
conversions. Channel-level decisions also ignore product-specific response.
See README for commands and current sample results.
