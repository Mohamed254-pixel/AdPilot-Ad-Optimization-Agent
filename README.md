# AdPilot — advertising data and performance analysis

This contribution supplies mock advertising data and descriptive performance
analysis. The existing agent, evaluation, prompt, and design placeholders are
preserved. Marketing Agent implementation, budget allocation, evaluation, and
presentation are outside this contribution.

## Fit with the group assignment

The assignment allows 14–30 days of data for three channels. This contribution
provides the 30-day option, an equal-spend starting dataset, CSV validation,
and descriptive metrics that teammates can use as inputs to their agent and
evaluation work. The performance CLI reports historical mock results; it does
not propose budgets, log agent decisions, or implement a learning loop.

Remaining group deliverables include the system prompt and guardrails, budget
decision tooling and rationale logs, evaluation routine, one-page design doc,
half-page scaling note, GitHub link and successful outputs, and a 2–3 minute
slide presentation. The group also needs member names and shared meeting
summaries with attendance, action items, and follow-ups. This contribution
does not complete those deliverables.

## Setup

Use Python 3.10 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Generate mock data

```bash
python data/generate_data.py
```

The checked-in `data/ad_performance.csv` contains 90 rows: 30 consecutive days
starting January 1, 2026, with one row per day for Search, Social, and Display.
Each channel spends $100 daily, giving $300 per day and $9,000 over 30 days.
Columns are `date`, `channel`, `spend`, `impressions`, `clicks`, `conversions`,
`campaign_id`, `campaign_name`, and `product_category`.
Traffic and response ranges differ by channel; these are synthetic examples,
not observed campaign results. The default random seed is 42.

Optional regeneration parameters:

```bash
python data/generate_data.py --start-date 2026-02-01 --seed 7 --output /tmp/ad_performance.csv
```

Use the default parameters to reproduce the checked-in CSV exactly.

### Cartside campaign context

The generator adds three illustrative campaigns: Cartside Produce Discovery,
Cartside Dairy & Eggs Discovery, and Cartside Pantry Staples Discovery. Produce,
Dairy & Eggs, and Pantry Staples are sample categories, not Cartside's verified
catalog. Edit `CAMPAIGNS` in `data/generate_data.py` to use confirmed categories.
Each stable campaign ID maps to one campaign name and product category.

Campaigns rotate daily, with the same campaign running on all three channels
on each date. Each campaign has ten days per channel, 30 rows, and $3,000 spend.
This preserves 90 rows and $300 daily spend, and avoids assigning a category
exclusively to one channel. Existing numeric mock performance is preserved;
category labels do not model real product demand or a causal category effect.
Use results as descriptive inputs for teammates' later recommendation work.
No recommendation or budget allocation logic is implemented here.

## Command-line performance demo

```bash
python -m analysis.performance
python -m analysis.performance --input /tmp/ad_performance.csv
python -m analysis.performance --group-by product_category
python -m analysis.performance --group-by campaign_id
python -m analysis.performance --group-by campaign_name
```

The demo validates the CSV and prints each channel plus a Total row with spend,
impressions, clicks, conversions, CTR, CVR, and CPA. Calculations use Pandas:

| Metric | Formula |
| --- | --- |
| CTR | total clicks / total impressions |
| CVR | total conversions / total clicks |
| CPA | total spend / total conversions |

Rates are calculated after aggregation, so the Total row uses weighted rates.
`calculate_performance(frame)` returns CTR and CVR as fractions; the CLI displays
percentages and dollar amounts. A zero denominator returns NaN, shown as N/A.
The optional `--group-by` selects channel, campaign ID, campaign name, or
product category. The Python function accepts the same `group_by` argument.
Campaign IDs are the stable grouping key; names shared by multiple IDs are
combined when grouping by campaign name. Legacy six-column CSVs still work
with channel summaries; context summaries require their grouping column.

`validate_data(frame)` rejects missing columns or fields, empty input, blank
dates or channels, invalid ISO dates, nonnumeric, infinite, or negative metrics,
fractional event counts, clicks exceeding impressions, and conversions exceeding
clicks. Custom input can cover any channels and dates; the 30-day, three-channel,
fixed-spend contract applies to the mock generator and is checked by tests.
When context columns are present, validation also rejects missing or blank
context fields. With all three context columns, it checks that each campaign ID
maps to exactly one campaign name and one product category.

## Tests

```bash
python -m pytest -q
```

Tests check the generated and saved data, daily spending and row counts,
reproducibility, validation failures, hand-calculated aggregates, weighted
ratios, and zero denominators. Existing project files remain in place; `main.py`
is preserved and the demo runs through `analysis.performance`.
