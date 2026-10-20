# AdPilot

AdPilot is a group project about using advertising data to decide where to spend
an ad budget. We’re using sample grocery campaigns for Cartside as our example.

So far, the project can create sample ad data, check it for errors, and show how
each advertising channel or grocery category performed. The agent that will
recommend budget changes is still to be built.

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

The tests check the 90-row dataset, daily spending, campaign labels, and metric
calculations. They also check that invalid data is rejected, including missing
values, negative numbers, clicks greater than ad views, and conversions greater
than clicks. Each campaign ID must have one consistent name and category.

The analysis still accepts CSVs with only the original six columns: `date`,
`channel`, `spend`, `impressions`, `clicks`, and `conversions`. Campaign or category
summaries need the matching extra column. If those extra fields are included,
they must not be blank.

## What’s left for the group?

The data and performance summaries are ready for the next part of the project.
The group still needs to build the agent’s instructions, budget recommendations,
decision explanations, and evaluation. The remaining submission work includes
the design document, cloud scaling note, meeting summaries, and a 2–3 minute
presentation with slides.
