# AdPilot

AdPilot is a group project about using advertising data to decide where to spend
an ad budget. We’re using sample grocery campaigns for Cartside as our example.

The project creates sample ad data, validates it, calculates performance, and
recommends an explainable next-day budget. The deterministic agent uses historical
and recent conversion performance, retains exploration funding, and checks its
recommendations against spending guardrails. No LLM API or ad-platform connection
is needed.

## What’s in the sample data?

The file `data/ad_performance.csv` contains 30 days of made-up advertising data,
starting January 1, 2026. It covers three channels:

- **Search:** ads shown in search results.
- **Social:** ads shown on social media.
- **Display:** banner and image ads shown on websites.

Each channel spends $100 per day. That’s $300 a day and $9,000 over the full
30 days, with 90 rows in the file.

The campaigns use three grocery categories: **Produce, Dairy & Eggs, and
Pantry Staples**. These are examples for the project, not a confirmed list of
Cartside’s products. A campaign is a named set of ads promoting one category.
Each day, the same campaign runs across all three channels. The campaigns take
turns, so each one runs for ten days and spends $3,000 in total.

Each row includes the date, channel, money spent, impressions, clicks,
conversions, campaign ID, campaign name, and product category. An impression is
one ad view. A conversion is the action the ad aims to produce, such as a
purchase. All of these numbers are simulated; they are not real Cartside results.

## Get started

You’ll need Python 3.10 or newer. Open a terminal in the project folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

These commands create a separate Python environment for the project and install
the packages it needs. On Windows, use `.venv\Scripts\activate` for the second
command.

## Run the optimization agent

```bash
python main.py
```

The report shows historical and recent performance, scores, current and
recommended budgets, reasons, an illustrative evaluation, and guardrail checks.
Use `--input path/to/file.csv` to read another dataset. Run inside the virtual
environment above to avoid conflicts with unrelated Python packages.

For the included data, the next-day plan is **Search $120, Social $100, Display
$80**, from an equal $100 baseline. Every allocation totals $300, reserves at
least $30 per channel, and changes each channel by at most 20%. Search wins from
its observed performance; channel names do not determine the recommendation.

### How the agent decides

1. Reuse `analysis.performance.calculate_performance()` for all validated metrics.
2. Blend each channel's historical and latest seven-calendar-day conversions per
   dollar and CVR with equal weights. The latest window ends at the dataset's
   latest date, not the computer's current date.
3. Divide each blended measure by the best channel's value. Score = **75% relative
   conversions per dollar + 25% relative CVR**. Conversions per dollar is inverse
   CPA, so CPA is not counted twice. CTR provides context rather than rewarding
   clicks alone. The weights are simple prototype policy choices, not learned.
4. Reserve $30 per channel and target the remaining $210 proportionally to score.
   Adjust targets within the $30 floor and +/-20% current-budget bounds while
   preserving the $300 total, including after rounding to cents.
5. Log a reason for each channel. Re-run with new observations and the actual
   current budgets to continue the lightweight learning loop.

By default, current budgets come from the latest observed day's channel spend.
The Python API also accepts an explicit allocation:

```python
from agents.marketing_agent import optimize_budget
result = optimize_budget(frame, current_budgets={"Search": 120, "Social": 100, "Display": 80})
print(result.decision_log)
```

All three channels and a valid $300 current allocation are required. Infeasible
constraints raise a clear error rather than silently violating a guardrail. Zero
conversions produce undefined CPA (`N/A` in the report); if all
conversion evidence is zero, the agent retains current budgets when feasible.
A channel missing recent observations uses its historical performance.

### Illustrative evaluation

`evaluation/evaluate.py` compares equal $100 allocations with the agent, using
the **same full-history conversions-per-dollar rates** for both. For this sample,
estimated daily conversions are **27.77 vs 30.83**, estimated CPA is **$10.80 vs
$9.73**, and estimated conversion lift is **11.02%**.

These are hypothetical estimates from training data, not measured future results
or causal evidence. They assume a linear spending response with unchanged rates,
no saturation, and no auction or cross-channel effects. Future observations or a
controlled experiment would be needed to establish actual improvement.

## Run the performance summary

The sample CSV is already included, so you can run this right away:

```bash
python -m analysis.performance
```

This prints results for Search, Social, and Display, followed by an overall
total. To compare grocery categories instead, run:

```bash
python -m analysis.performance --group-by product_category
```

You can also group by campaign using `--group-by campaign_id` or
`--group-by campaign_name`. To read a different CSV, add `--input path/to/file.csv`.

Here’s what the main numbers mean:

| Metric | What it tells you | Calculation |
| --- | --- | --- |
| CTR (click-through rate) | How often an ad view led to a click | Clicks ÷ impressions |
| CVR (conversion rate) | How often a click led to a conversion | Conversions ÷ clicks |
| CPA (cost per acquisition) | How much was spent for each conversion | Spend ÷ conversions |

The program adds up the counts before calculating these rates, including for
the overall total. If a rate can’t be calculated because its divisor is zero,
the summary shows `N/A`.

With the included data, total spend is **$9,000**, with **14,826 clicks** and
**833 conversions**. The overall CTR is **1.78%**, CVR is **5.62%**, and CPA is
**$10.80**. These results demonstrate the calculations; they don’t tell us how
real grocery ads would perform.

## Create the sample data again

```bash
python data/generate_data.py
```

This replaces `data/ad_performance.csv` with the same sample data. The generator
uses a fixed random seed of 42, so the default results stay the same each time.
To try a different start date or set of random numbers and save a separate file:

```bash
python data/generate_data.py --start-date 2026-02-01 --seed 7 --output data/another_sample.csv
```

To change the category names, edit `CAMPAIGNS` in `data/generate_data.py` and
run the generator again. Category labels provide context; the generator does
not simulate how demand differs between grocery categories.

## Check that everything works

```bash
python -m pytest -q
```

The tests check the 90-row dataset, daily spending, campaign labels, metric
calculations, optimization constraints, recent changes, explanations, evaluation,
and CLI execution. They also check that invalid data is rejected, including missing
values, negative numbers, clicks greater than ad views, and conversions greater
than clicks. Each campaign ID must have one consistent name and category.

The analysis still accepts CSVs with only the original six columns: `date`,
`channel`, `spend`, `impressions`, `clicks`, and `conversions`. Campaign or category
summaries need the matching extra column. If those extra fields are included,
they must not be blank.

## What’s left for the group?

The core agent, instructions, recommendations, decision explanations, evaluation,
and design notes are implemented. Remaining submission work includes the cloud
scaling note, meeting summaries, and a 2–3 minute presentation with slides.
