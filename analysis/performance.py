"""Validate advertising data and print channel and overall performance."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["date", "channel", "spend", "impressions", "clicks", "conversions"]
CONTEXT_COLUMNS = ["campaign_id", "campaign_name", "product_category"]
GROUP_COLUMNS = ["channel", *CONTEXT_COLUMNS]
METRICS = ["spend", "impressions", "clicks", "conversions"]
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data" / "ad_performance.csv"


def validate_data(frame: pd.DataFrame) -> None:
    """Raise ValueError for missing, invalid, or inconsistent source values."""
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Data must contain at least one row")
    for column in CONTEXT_COLUMNS:
        if column in frame and (
            frame[column].isna().any()
            or frame[column].astype(str).str.strip().eq("").any()
        ):
            raise ValueError(f"{column} must not contain missing or blank fields")
    if set(CONTEXT_COLUMNS).issubset(frame.columns):
        mappings = frame.groupby("campaign_id")[["campaign_name", "product_category"]].nunique()
        if mappings.gt(1).any().any():
            raise ValueError("Each campaign_id must map to one campaign_name and product_category")
    if frame[COLUMNS].isna().any().any():
        raise ValueError("Missing fields are not allowed")
    if frame[["date", "channel"]].apply(
        lambda column: column.astype(str).str.strip().eq("")
    ).any().any():
        raise ValueError("Blank date or channel fields are not allowed")
    if pd.to_datetime(frame["date"], format="ISO8601", errors="coerce").isna().any():
        raise ValueError("Dates must be valid")
    for column in METRICS:
        if not pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
            raise ValueError(f"{column} must be numeric")
        if not np.isfinite(frame[column]).all() or (frame[column] < 0).any():
            raise ValueError(f"{column} must be finite and nonnegative")
    for column in ("impressions", "clicks", "conversions"):
        if (frame[column] % 1 != 0).any():
            raise ValueError(f"{column} must contain whole counts")
    if (frame["clicks"] > frame["impressions"]).any():
        raise ValueError("Clicks cannot exceed impressions")
    if (frame["conversions"] > frame["clicks"]).any():
        raise ValueError("Conversions cannot exceed clicks")


def calculate_performance(frame: pd.DataFrame, group_by: str = "channel") -> pd.DataFrame:
    """Aggregate counts first, then calculate CTR, CVR, and CPA.

    CTR and CVR are fractions. Undefined ratios are NaN.
    """
    validate_data(frame)
    if group_by not in GROUP_COLUMNS:
        raise ValueError(f"Unsupported grouping: {group_by}")
    if group_by not in frame:
        raise ValueError(f"Missing grouping column: {group_by}")
    summary = frame.groupby(group_by, sort=True)[METRICS].sum()
    total = frame[METRICS].agg(["sum"])
    total.index = pd.Index(["Total"], name=group_by)
    summary = pd.concat([summary, total])
    summary["CTR"] = summary["clicks"] / summary["impressions"].replace(0, np.nan)
    summary["CVR"] = summary["conversions"] / summary["clicks"].replace(0, np.nan)
    summary["CPA"] = summary["spend"] / summary["conversions"].replace(0, np.nan)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--group-by", choices=GROUP_COLUMNS, default="channel")
    args = parser.parse_args()
    try:
        summary = calculate_performance(pd.read_csv(args.input), group_by=args.group_by)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(summary.to_string(formatters={
        "spend": lambda value: f"${value:,.2f}",
        "CTR": lambda value: f"{value:.2%}",
        "CVR": lambda value: f"{value:.2%}",
        "CPA": lambda value: f"${value:,.2f}",
    }, na_rep="N/A"))


if __name__ == "__main__":
    main()
