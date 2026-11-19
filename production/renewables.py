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


def _month_start(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Start of the Danish-time month for each UTC hour."""
    local = index.tz_localize("UTC").tz_convert("Europe/Copenhagen")
    return local.tz_localize(None).to_period("M").to_timestamp()


def installed_capacity_hourly(cfg: dict, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Installed capacity (MW) in force in each hour, from the monthly Energinet data."""
    month_start = _month_start(index)
    return pd.DataFrame({
        carrier: monthly_capacity(cfg, column).reindex(month_start).to_numpy()
        for carrier, column in CAPACITY_COLUMNS.items()
    }, index=index)


def capacity_factors(cfg: dict, national: pd.DataFrame) -> pd.DataFrame:
    """Hourly capacity factor: actual output / capacity installed that month."""
    cap = installed_capacity_hourly(cfg, national.index)
    return national[list(CAPACITY_COLUMNS)] / cap


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
    cf = capacity_factors(cfg, national)
    out = {}
    for carrier, column in CAPACITY_COLUMNS.items():
        p_nom = float(monthly_capacity(cfg, column).iloc[-1])
        p_max_pu = (national[carrier] / p_nom).clip(lower=0.0, upper=1.0)
        out[carrier] = {
            "p_nom": p_nom * scale[carrier],
            "p_max_pu": p_max_pu,
            "capacity_factor": float(cf[carrier].mean()),
        }
    return out
