"""Download the raw 2025 input data from Energinet's Energi Data Service.

Source: https://www.energidataservice.dk (Energinet, Danish TSO). Free, no API key.

Datasets
--------
ProductionConsumptionSettlement  hourly settled production, consumption and
                                 exchange per price area (DK1, DK2)
Elspotprices                     hourly day-ahead prices (up to 2025-09-30)
DayAheadPrices                   day-ahead prices, 15-min since 2025-10-01
GasDailyBalancingPrice           daily Danish gas price (EEX spot index)
CapacityPerMunicipality          monthly installed wind/solar capacity

Usage:  python data/download.py            (skips files that already exist)
        python data/download.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_config  # noqa: E402

API = "https://api.energidataservice.dk/dataset/"


def fetch(dataset: str, start: str, end: str, columns: list[str] | None = None,
          filters: dict | None = None) -> pd.DataFrame:
    """Fetch every record of `dataset` between `start` and `end` (Danish local time)."""
    params = {"start": start, "end": end, "limit": 0}
    if columns:
        params["columns"] = ",".join(columns)
    if filters:
        params["filter"] = json.dumps(filters)
    r = requests.get(API + dataset, params=params, timeout=300)
    r.raise_for_status()
    records = r.json()["records"]
    print(f"  {dataset}: {len(records)} records")
    return pd.DataFrame.from_records(records)


def main(force: bool = False) -> None:
    cfg = load_config()
    year = cfg["year"]
    raw = ROOT / cfg["paths"]["raw"]
    raw.mkdir(parents=True, exist_ok=True)
    start, end = f"{year}-01-01T00:00", f"{year + 1}-01-01T00:00"
    areas = {"PriceArea": ["DK1", "DK2"]}

    jobs = {
        "production_consumption.csv": lambda: fetch(
            "ProductionConsumptionSettlement", start, end, filters=areas),
        "prices_hourly.csv": lambda: fetch(
            "Elspotprices", start, end, filters=areas),
        "prices_dayahead.csv": lambda: fetch(
            "DayAheadPrices", start, end, filters=areas),
        "gas_price_daily.csv": lambda: fetch(
            "GasDailyBalancingPrice", f"{year - 1}-12-01", f"{year + 1}-01-01"),
        "capacity_municipality.csv": lambda: fetch(
            "CapacityPerMunicipality", f"{year - 1}-12-01", f"{year + 1}-01-01"),
    }
    for fname, job in jobs.items():
        path = raw / fname
        if path.exists() and not force:
            print(f"  {fname}: exists, skipping")
            continue
        df = job()
        df.to_csv(path, index=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--force", action="store_true", help="re-download existing files")
    main(p.parse_args().force)
