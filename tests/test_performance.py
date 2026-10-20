"""Checks for generated data, validation, and aggregate calculations."""

from pathlib import Path

import pandas as pd
import pytest

from analysis.performance import COLUMNS, CONTEXT_COLUMNS, calculate_performance, validate_data
from data.generate_data import generate_data


def test_generated_data_contract():
    frame = generate_data()
    validate_data(frame)
    assert list(frame.columns) == COLUMNS + CONTEXT_COLUMNS
    assert len(frame) == 90
    assert frame["date"].nunique() == 30
    assert set(frame["channel"]) == {"Search", "Social", "Display"}
    assert not frame.duplicated(["date", "channel"]).any()
    assert frame.groupby("date").size().eq(3).all()
    assert frame["spend"].eq(100).all()
    assert frame.groupby("date")["spend"].sum().eq(300).all()
    dates = pd.to_datetime(frame["date"].unique()).sort_values()
    assert (dates[1:] - dates[:-1] == pd.Timedelta(days=1)).all()
    pd.testing.assert_frame_equal(frame, generate_data())


def test_campaign_context_is_comparable_across_channels():
    frame = generate_data()
    assert frame["campaign_id"].nunique() == 3
    assert frame["product_category"].nunique() == 3
    assert frame.groupby("date")["campaign_id"].nunique().eq(1).all()
    for _, campaign in frame.groupby("campaign_id"):
        assert campaign["campaign_name"].nunique() == 1
        assert campaign["product_category"].nunique() == 1
        assert campaign.groupby("channel").size().eq(10).all()


@pytest.mark.parametrize("column", CONTEXT_COLUMNS)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_invalid_context_rejected(column, value):
    frame = generate_data()
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        validate_data(frame)


def test_inconsistent_campaign_mapping_rejected():
    frame = generate_data()
    frame.loc[0, "product_category"] = "Different category"
    with pytest.raises(ValueError, match="must map"):
        validate_data(frame)


@pytest.mark.parametrize("group_by", CONTEXT_COLUMNS)
def test_context_grouping_matches_source_totals(group_by):
    frame = generate_data()
    summary = calculate_performance(frame, group_by=group_by)
    expected = frame.groupby(group_by)[["spend", "impressions", "clicks", "conversions"]].sum()
    pd.testing.assert_frame_equal(summary.drop(index="Total")[expected.columns], expected)
    first = expected.index[0]
    assert summary.loc[first, "CPA"] == pytest.approx(expected.loc[first, "spend"] / expected.loc[first, "conversions"])
    assert summary.loc["Total", "spend"] == 9000


def test_legacy_data_still_supported_and_missing_grouping_rejected():
    legacy = generate_data()[COLUMNS]
    assert calculate_performance(legacy).loc["Total", "spend"] == 9000
    with pytest.raises(ValueError, match="Missing grouping column"):
        calculate_performance(legacy, group_by="product_category")
    with pytest.raises(ValueError, match="Unsupported grouping"):
        calculate_performance(legacy, group_by="unknown")


def test_saved_csv_matches_generator():
    saved = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "ad_performance.csv")
    validate_data(saved)
    pd.testing.assert_frame_equal(saved, generate_data())


@pytest.mark.parametrize("column,value", [
    ("spend", -1), ("impressions", -1), ("clicks", -1),
    ("conversions", -1), ("clicks", 1000000), ("conversions", 1000000),
    ("date", None), ("channel", ""), ("date", "invalid"),
    ("spend", float("inf")), ("clicks", 1.5),
])
def test_invalid_values_rejected(column, value):
    frame = generate_data()
    if column in {"spend", "impressions", "clicks", "conversions"}:
        frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        validate_data(frame)


@pytest.mark.parametrize("column", COLUMNS)
def test_missing_fields_rejected(column):
    frame = generate_data()
    frame.loc[0, column] = None
    with pytest.raises(ValueError):
        validate_data(frame)


def test_missing_columns_and_empty_data_rejected():
    with pytest.raises(ValueError):
        validate_data(generate_data().drop(columns="spend"))
    with pytest.raises(ValueError):
        validate_data(generate_data().iloc[:0])


def test_aggregate_calculations_use_weighted_rates():
    frame = pd.DataFrame([
        ["2026-01-01", "Search", 100, 1000, 100, 10],
        ["2026-01-02", "Search", 100, 9000, 90, 9],
        ["2026-01-01", "Social", 100, 2000, 100, 5],
    ], columns=COLUMNS)
    summary = calculate_performance(frame)
    search = summary.loc["Search"]
    assert search[["spend", "impressions", "clicks", "conversions"]].tolist() == [200, 10000, 190, 19]
    assert search["CTR"] == pytest.approx(190 / 10000)
    assert search["CVR"] == pytest.approx(19 / 190)
    assert search["CPA"] == pytest.approx(200 / 19)
    total = summary.loc["Total"]
    assert total[["spend", "impressions", "clicks", "conversions"]].tolist() == [300, 12000, 290, 24]
    assert total["CTR"] == pytest.approx(290 / 12000)
    assert total["CVR"] == pytest.approx(24 / 290)
    assert total["CPA"] == pytest.approx(300 / 24)


def test_zero_denominators_are_undefined():
    frame = pd.DataFrame([["2026-01-01", "Search", 100, 0, 0, 0]], columns=COLUMNS)
    summary = calculate_performance(frame)
    assert summary[["CTR", "CVR", "CPA"]].isna().all().all()
