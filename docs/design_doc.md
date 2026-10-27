# AdPilot design document

**Purpose and inputs.** AdPilot recommends next-day advertising budgets across
Search, Social, and Display within a fixed $300 daily total. It is a deterministic
Python decision-support prototype using simulated grocery campaigns, with no LLM
or advertising-platform connection. The dataset contains 90 observations covering
30 days, including date, channel, spend, impressions, clicks, conversions, and
campaign/category labels.

**Processing.** `analysis/performance.py` validates required fields, nonnegative
values, whole counts, and consistent campaign labels. It rejects clicks exceeding
impressions and conversions exceeding clicks. Counts are summed before calculating
CTR (clicks/impressions), CVR (conversions/clicks), and CPA (spend/conversions).
Undefined rates remain unavailable rather than implying zero cost.

**Decision policy.** `agents/marketing_agent.py` blends historical and latest
seven-calendar-day conversions per dollar and CVR equally. Each blended measure
is normalized against its best channel. The score weights relative conversions
per dollar at 75% and relative CVR at 25%; CTR provides context. Missing recent
rates fall back to history. All-zero scores retain current budgets where feasible.
The weights are fixed policy choices, not learned parameters.

**Budget constraints.** Initial targets reserve $30 per channel and distribute
the remaining $210 proportionally to scores. Bounded fitting adjusts targets to
preserve exactly $300, a $30 minimum, and changes within 20% of current budgets.
Currency aggregation uses decimal arithmetic; final allocations use whole cents
and undergo guardrail checks. Infeasible inputs raise errors. Current budgets
come from latest-day spending unless explicitly supplied through the Python API.

**Outputs and feedback.** `main.py` prints performance, recommended budgets,
explanations, evaluation, and guardrails. Structured decision records include
dates, previous/new budgets, changes, metrics, and reasons. New observations and
actual current budgets update subsequent runs; unchanged inputs produce identical
results. The program does not apply budgets or persist an operational history.

**Evaluation and limitations.** Automated tests cover validation, scoring,
allocation, rounding, explanations, and CLI execution. Holdout evaluation selects
a fixed allocation using January 1–21 and estimates performance on January 22–30:
251.00 baseline versus 280.40 agent conversions, or 11.71% estimated lift. These
mock-data estimates assume linear spending response, omit saturation and
cross-channel effects, and do not establish real improvement. The heuristic does
not guarantee maximum conversions or model product-specific demand.
