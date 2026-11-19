"""Actual 2025 day-ahead prices for comparison with the model.

Jan-Sep come hourly (Energinet `Elspotprices`); from 1 Oct 2025 the market
runs in 15-minute steps (`DayAheadPrices`), which are averaged to the hour.
The single-node model is compared with a national price: DK1 and DK2 weighted
by each area's gross consumption in that hour.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def actual_prices(cfg: dict) -> pd.DataFrame:
    """Hourly EUR/MWh with columns DK1, DK2, DK (consumption-weighted)."""
    raw = ROOT / cfg["paths"]["raw"]
    h = pd.read_csv(raw / "prices_hourly.csv", parse_dates=["HourUTC"])
    h = h.pivot_table(index="HourUTC", columns="PriceArea", values="SpotPriceEUR")
    q = pd.read_csv(raw / "prices_dayahead.csv", parse_dates=["TimeUTC"])
    q["HourUTC"] = q["TimeUTC"].dt.floor("h")
    q = q.pivot_table(index="HourUTC", columns="PriceArea", values="DayAheadPriceEUR", aggfunc="mean")
    prices = pd.concat([h, q[q.index > h.index.max()]]).sort_index()

    s = pd.read_csv(raw / "production_consumption.csv", parse_dates=["HourUTC"])
    w = s.pivot_table(index="HourUTC", columns="PriceArea", values="GrossConsumptionMWh")
    w = w.reindex(prices.index)
    prices["DK"] = (prices["DK1"] * w["DK1"] + prices["DK2"] * w["DK2"]) / (w["DK1"] + w["DK2"])
    prices.index.name = "snapshot"
    prices.columns.name = None
    return prices
