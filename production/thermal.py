"""Thermal power plants: capacity, hourly marginal cost and CHP must-run.

Plants are grouped by fuel and size in production/thermal_fleet.csv.

Marginal cost (EUR per MWh of electricity):
    (fuel price + CO2 price x emission factor) / electrical efficiency + variable O&M

Must-run: Danish CHP plants are held on by district heating demand. For each
month, the floor is a low quantile of the actual thermal output in that month.
Waste plants take the first part of the floor; the rest is shared across the
other CHP groups in proportion to their capacity.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FLEET_FILE = Path(__file__).with_name("thermal_fleet.csv")


def load_fleet() -> pd.DataFrame:
    fleet = pd.read_csv(FLEET_FILE, index_col="group")
    fleet["available_until"] = pd.to_datetime(fleet["available_until"])
    return fleet


def _local_time(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_localize("UTC").tz_convert("Europe/Copenhagen").tz_localize(None)


def gas_price_hourly(cfg: dict, index: pd.DatetimeIndex) -> pd.Series:
    """Daily Danish gas price (EEX spot index, EUR/MWh), repeated for each hour."""
    path = ROOT / cfg["paths"]["raw"] / "gas_price_daily.csv"
    g = pd.read_csv(path, parse_dates=["GasDay"]).set_index("GasDay").sort_index()
    daily = g["EEXSpotIndexEUR_MWh"]
    days = _local_time(index).normalize()
    price = daily.reindex(days.unique()).ffill().bfill()  # fill any missing days
    return pd.Series(price.reindex(days).to_numpy(), index=index, name="gas")


def co2_price_hourly(cfg: dict, index: pd.DatetimeIndex) -> pd.Series:
    monthly = cfg["co2_price_monthly"]
    months = _local_time(index).month
    return pd.Series([monthly[m - 1] for m in months], index=index, name="co2")


def marginal_costs(cfg: dict, fleet: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    gas = gas_price_hourly(cfg, index)
    co2 = co2_price_hourly(cfg, index)
    costs = {}
    for group, row in fleet.iterrows():
        fuel = row["fuel"]
        fuel_price = gas if fuel == "gas" else cfg["fuel_prices"][fuel]
        ef = cfg["emission_factors"][fuel]
        costs[group] = (fuel_price + co2 * ef) / row["efficiency"] + row["vom_eur_per_mwh"]
    return pd.DataFrame(costs, index=index)


def availability(fleet: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """1 while a group is in service, 0 after its available_until date."""
    local = _local_time(index)
    avail = {}
    for group, row in fleet.iterrows():
        until = row["available_until"]
        on = pd.Series(1.0, index=index)
        if pd.notna(until):
            on[local >= until + pd.Timedelta(days=1)] = 0.0
        avail[group] = on
    return pd.DataFrame(avail)


def must_run(cfg: dict, fleet: pd.DataFrame, avail: pd.DataFrame,
             actual_thermal: pd.Series, demand: pd.Series) -> pd.DataFrame:
    """Minimum output per group as a share of capacity (p_min_pu)."""
    q = cfg["must_run"]["quantile"]
    months = _local_time(actual_thermal.index).month
    floor_month = actual_thermal.groupby(months).quantile(q)
    floor = pd.Series(floor_month.reindex(months).to_numpy(), index=actual_thermal.index)
    floor = floor.clip(upper=demand)  # never force more than demand

    p_min = pd.DataFrame(0.0, index=floor.index, columns=fleet.index)
    chp = fleet[fleet["chp"]]

    waste = chp.index[chp["fuel"] == "waste"]
    waste_cap = (avail[waste] * chp.loc[waste, "p_nom_mw"]).sum(axis=1)
    from_waste = floor.clip(upper=waste_cap * cfg["must_run"]["waste_share"])
    for g in waste:
        p_min[g] = (from_waste / waste_cap.where(waste_cap > 0)).fillna(0) * avail[g]

    rest = floor - from_waste
    others = chp.index.difference(waste)
    other_mw = (avail[others] * chp.loc[others, "p_nom_mw"]).sum(axis=1)
    share = (rest / other_mw).clip(upper=1.0)
    for g in others:
        p_min[g] = share * avail[g]
    return p_min.clip(upper=avail)
