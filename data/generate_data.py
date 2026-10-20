"""Generate a reproducible, 30-day mock advertising dataset."""

import argparse
from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd

CHANNELS = ("Search", "Social", "Display")
# Illustrative Cartside categories, not a verified product catalog.
CAMPAIGNS = (
    ("cartside-produce", "Cartside Produce Discovery", "Produce"),
    ("cartside-dairy-eggs", "Cartside Dairy & Eggs Discovery", "Dairy & Eggs"),
    ("cartside-pantry-staples", "Cartside Pantry Staples Discovery", "Pantry Staples"),
)
OUTPUT_PATH = Path(__file__).resolve().parent / "ad_performance.csv"


def generate_data(start_date: str = "2026-01-01", seed: int = 42) -> pd.DataFrame:
    """Return 90 rows with exactly $100 per channel per day."""
    start = date.fromisoformat(start_date)
    rng = random.Random(seed)
    # Different mock traffic and response ranges per channel.
    profiles = {
        "Search": (2500, 5000, 0.04, 0.07, 0.06, 0.12),
        "Social": (6000, 10000, 0.015, 0.03, 0.02, 0.06),
        "Display": (12000, 20000, 0.003, 0.01, 0.01, 0.04),
    }
    rows = []
    for offset in range(30):
        # One campaign per day across every channel; ten days per campaign.
        campaign_id, campaign_name, category = CAMPAIGNS[offset % len(CAMPAIGNS)]
        for channel in CHANNELS:
            low, high, ctr_low, ctr_high, cvr_low, cvr_high = profiles[channel]
            impressions = rng.randint(low, high)
            clicks = round(impressions * rng.uniform(ctr_low, ctr_high))
            conversions = round(clicks * rng.uniform(cvr_low, cvr_high))
            rows.append({
                "date": (start + timedelta(days=offset)).isoformat(),
                "channel": channel,
                "spend": 100.0,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "product_category": category,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2026-01-01", help="First day (YYYY-MM-DD)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    frame = generate_data(args.start_date, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"Saved {len(frame)} rows to {args.output}")


if __name__ == "__main__":
    main()
