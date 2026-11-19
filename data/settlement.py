"""Read Energinet's hourly settlement data and sum DK1 + DK2 into one national series."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

EXCHANGE = ["ExchangeNO_MWh", "ExchangeSE_MWh", "ExchangeGE_MWh",
            "ExchangeNL_MWh", "ExchangeGB_MWh"]  # positive = import
OFFSHORE = ["OffshoreWindLt100MW_MWh", "OffshoreWindGe100MW_MWh"]
ONSHORE = ["OnshoreWindLt50kW_MWh", "OnshoreWindGe50kW_MWh"]
SOLAR = ["SolarPowerLt10kW_MWh", "SolarPowerGe10Lt40kW_MWh",
         "SolarPowerGe40kW_MWh", "SolarPowerSelfConMWh"]
THERMAL = ["CentralPowerMWh", "LocalPowerMWh", "CommercialPowerMWh",
           "LocalPowerSelfConMWh"]
OTHER = ["HydroPowerMWh", "UnknownProdMWh"]


def national_hourly(cfg: dict) -> pd.DataFrame:
    """National hourly totals in MW, indexed by UTC hour.

    Columns: consumption, net_import, onshore, offshore, solar, thermal, other.
    Self-consumed production is included, because Energinet's gross
    consumption includes it (the balance only closes with it).
    """
    path = ROOT / cfg["paths"]["raw"] / "production_consumption.csv"
    d = pd.read_csv(path, parse_dates=["HourUTC"])
    n = d.groupby("HourUTC").sum(numeric_only=True).sort_index()
    out = pd.DataFrame({
        "consumption": n["GrossConsumptionMWh"],
        "net_import": n[EXCHANGE].sum(axis=1),
        "onshore": n[ONSHORE].sum(axis=1),
        "offshore": n[OFFSHORE].sum(axis=1),
        "solar": n[SOLAR].sum(axis=1),
        "thermal": n[THERMAL].sum(axis=1),
        "other": n[OTHER].sum(axis=1),
    })
    out.index.name = "snapshot"
    expected = pd.date_range(f"{cfg['year'] - 1}-12-31 23:00", periods=len(out), freq="h")
    if len(out) != 8760 or not out.index.equals(expected):
        raise ValueError("settlement data does not cover every hour of the year")
    return out
