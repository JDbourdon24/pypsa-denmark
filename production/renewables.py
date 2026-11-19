"""Wind and solar capacity and hourly availability.

Availability (p_max_pu) = actual 2025 output / installed capacity that month.
Installed capacity is Energinet's monthly CapacityPerMunicipality, summed over
all municipalities. Actual output is curtailment-free enough for this purpose;
the model can still curtail below it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

CAPACITY_COLUMNS = {
    "onshore": "OnshoreWindCapacity",
    "offshore": "OffshoreWindCapacity",
    "solar": "SolarPowerCapacity",
}


def monthly_capacity(cfg: dict, column: str) -> pd.Series:
    path = ROOT / cfg["paths"]["raw"] / "capacity_municipality.csv"
    c = pd.read_csv(path, parse_dates=["Month"]).groupby("Month")[column].sum()
    return c.sort_index()


def build_renewables(cfg: dict, national: pd.DataFrame) -> dict[str, dict]:
    """Return {carrier: {"p_nom": MW, "p_max_pu": Series}} for onshore, offshore, solar.

    p_nom is the year-end capacity times the scenario scale factor. Within the
    year, capacity changes are folded into p_max_pu, so output in each hour
    matches actual 2025 output when the scale factor is 1.
    """
    scale = {
        "onshore": cfg["scenario"]["wind_scale"]["onshore"],
        "offshore": cfg["scenario"]["wind_scale"]["offshore"],
        "solar": cfg["scenario"]["solar_scale"],
    }
    # Capacity is reported at the start of each month; map each hour to its month.
    # Hours are UTC; the first hour (31 Dec 23:00 UTC) belongs to January in Danish time.
    local_month = national.index.tz_localize("UTC").tz_convert("Europe/Copenhagen")
    month_start = local_month.tz_localize(None).to_period("M").to_timestamp()

    out = {}
    for carrier, column in CAPACITY_COLUMNS.items():
        cap = monthly_capacity(cfg, column)
        cap_hourly = pd.Series(cap.reindex(month_start).to_numpy(), index=national.index)
        p_nom = float(cap.iloc[-1])
        p_max_pu = (national[carrier] / p_nom).clip(lower=0.0, upper=1.0)
        out[carrier] = {
            "p_nom": p_nom * scale[carrier],
            "p_max_pu": p_max_pu,
            "capacity_factor": float((national[carrier] / cap_hourly).mean()),
        }
    return out
