# AdPilot cloud scaling note

## Current prototype and proposed deployment

AdPilot currently runs locally on 90 rows of simulated advertising data. It
validates aggregate observations, calculates channel metrics, and recommends
next-day budgets for Search, Social, and Display. Its policy is deterministic
Python, with no LLM, external API, or model-training dependency. The cloud design
below is a proposal; cloud infrastructure and advertising-platform integration
are not implemented in this repository.

For this workload, one scheduled batch job is sufficient. A continuously running
web service or distributed processing cluster would add unnecessary complexity.

```text
Daily aggregate CSV + approved current budgets
                    |
                    v
Versioned object storage
                    |
                    v
Scheduler -> Python batch worker
             validate -> calculate -> score -> allocate -> check guardrails
                    |
                    v
Stored decision CSV + run metadata + report
                    |
                    v
Human review of next-day recommendations
```

## Daily execution and storage

Package the application and a tested set of Python dependencies in a container.
A scheduler starts the container after the previous day's data is complete.
The worker downloads an immutable input snapshot to its working directory and
uses the existing analysis and agent modules. `python main.py --input <file>`
already prints a report for a local CSV; cloud downloads, uploads, scheduling,
and persistent decision storage require a small deployment wrapper.

Keep raw snapshots, reports, and decision records in separate storage prefixes.
Identify every run by account, observation date, input version, policy version,
and application commit. Store the `OptimizationResult.decision_log` as CSV along
with guardrail results, observation dates, actual current budgets, and a success
or failure status. This makes each recommendation traceable and reproducible.

Use `optimize_budget(frame, current_budgets=...)` when approved budgets differ
from observed spend. Actual spend can be below the assigned budget, so the
latest day's spend is not always a suitable production budget reference.
The existing policy requires exactly three channels and a $300 total. Supporting
different account budgets or channel sets requires parameterizing the policy
and extending its validation and tests before deployment.

## Reliability and data quality

Before scoring, apply the existing field and metric validation. The deployment
wrapper should also check source freshness, daily completeness, and duplicate
record identifiers. Aggregate campaign rows into channel totals rather than
treating multiple legitimate campaigns as duplicate observations. Define record
identity with the data supplier, including campaign identity where available.

Publish a recommendation only after every guardrail passes: exactly $300 in
whole cents, at least $30 per channel, positive allocations, and changes within
20% of actual current budgets. Missing, stale, or invalid inputs and infeasible
allocations should produce a failed run for review, with no new approved plan.
Do not silently substitute a previous plan as a fresh recommendation.

Retry temporary storage or worker failures with bounded retries. Data validation
errors need corrected inputs rather than repeated execution. Use a unique run
key and publish completed outputs atomically so retries cannot create multiple
approved decisions. Permit only one active decision run per account and date.
Retain earlier versions when corrected data causes a rerun.

## Scaling as usage grows

Scale across independent accounts using a work queue and multiple workers, with
account-specific storage and configuration. Keep each account's decision in one
worker so budgets and evidence cannot mix across accounts.

At larger data volumes, partition stored observations by account and date. The
current implementation loads the full CSV into pandas memory, so simply adding
workers will not solve one oversized account history. Introduce incremental
daily channel aggregates and cumulative totals, preserving the latest seven
calendar days for recent metrics. Sum spend and counts before calculating CTR,
CVR, CPA, and conversions per dollar; averaging daily percentages changes the
policy. Use integer cents or exact decimal arithmetic for currency aggregation.
Keep raw data for audits and verify incremental results against full-history
calculations before switching implementations.

## Monitoring, access, and cost

Record run duration, input row count, latest observation date, validation errors,
guardrail failures, and allocation changes. Alert the operator when an expected
daily run is missing or fails. Store execution logs separately from the decision
records so operational failures and policy decisions can be inspected together.

Use a dedicated service identity with access only to the required input and
output locations. Separate accounts' data, encrypt storage and transport, and
retain only aggregate advertising fields. If future connectors require
credentials, keep them in managed secret storage rather than source files.

Batch execution avoids paying for an idle service. Control costs through worker
resource limits, bounded retries, storage retention, and monitoring of runtime
and data growth. Measure representative workloads before selecting capacity;
the repository contains no cloud benchmark or verified hosting-cost estimate.

## Evaluation and rollout

Run the automated tests and sample report before releasing a container. Keep
holdout evaluation separate from the daily recommendation job: the current
holdout script trains on January 1–21 and evaluates a frozen allocation on
January 22–30, writing result CSVs. Its 11.71% estimated conversion lift uses
unseen mock-data days and a linear spend-response assumption. It does not show
measured advertising improvement or evaluate daily retraining.

Start in recommendation-only mode with human review, matching today's behavior.
A future live integration would need approval tracking, application receipts,
and reconciliation of actual platform budgets before the next run. Validate
real-world performance through an appropriately designed experiment before
claiming actual lift. Cloud deployment changes how the program runs; it does
not remove the policy's evaluation limits.
