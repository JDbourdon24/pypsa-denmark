"""Electricity demand the Danish system must cover itself, hourly, in MW.

    demand = gross consumption - net imports - hydro/other small production

Gross consumption (Energinet) already contains grid losses and electric
boilers and heat pumps (power-to-heat). Net imports are fixed at their actual
2025 values, which is how the isolated model stays in balance. What remains
must be covered by wind, solar and thermal plants in the model.
"""

from __future__ import annotations

import pandas as pd


def build_demand(national: pd.DataFrame) -> pd.Series:
    demand = national["consumption"] - national["net_import"] - national["other"]
    if (demand <= 0).any():
        raise ValueError("demand after net imports is not positive in some hours")
    return demand.rename("demand")


def balance_residual(national: pd.DataFrame) -> pd.Series:
    """Actual supply minus demand; should be close to zero (data consistency check)."""
    supply = national[["onshore", "offshore", "solar", "thermal"]].sum(axis=1)
    return (supply - build_demand(national)).rename("balance_residual")
