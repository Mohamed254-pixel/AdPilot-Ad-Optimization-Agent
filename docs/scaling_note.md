# AdPilot cloud scaling note

AdPilot currently runs locally; cloud deployment is proposed. Package its Python
code and tested dependencies in a container, then schedule one daily batch job
after aggregate advertising data is complete. A deployment wrapper would download
a versioned CSV, run validation and optimization, and upload the decision CSV,
report, guardrail results, and input/code versions to object storage. Supply actual
approved budgets when they differ from observed spending.

Reject stale, incomplete, or invalid inputs and publish recommendations only when
all budget guardrails pass. Use unique account/date/input-version run keys,
atomic output publication, and bounded retries to prevent duplicate decisions.
Monitor freshness, runtime, failures, and allocation changes; alert on missed runs.

Scale across accounts with queued jobs and isolated workers. For larger histories,
partition by account/date and maintain daily aggregates, cumulative totals, and
the latest seven calendar days. Sum counts before calculating rates and preserve
exact currency arithmetic. Different budgets or channel sets require policy changes.

Restrict service access, encrypt data, and store connector credentials in managed
secret storage. Batch execution and retention limits control costs. Begin with
human-reviewed recommendations. Cloud hosting does not validate the simulated
11.71% holdout lift; actual improvement requires real-world evaluation.
