"""Build and solve the single-node PyPSA model of Denmark for one year.

    python data/download.py          # once, fetches the raw data
    python main.py                   # baseline (config/config.yaml)
    python main.py --wind-scale 2    # same, with twice the wind capacity

Results go to results/<scenario name>/.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import pypsa

pypsa.options.api.legacy_string_dtype = True

from config import load_config
from data.settlement import national_hourly
from demand.demand import balance_residual, build_demand
from production.renewables import build_renewables
from production.thermal import availability, load_fleet, marginal_costs, must_run
from validation.prices import actual_prices

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("pypsa-denmark")


def build_network(cfg: dict) -> tuple[pypsa.Network, dict]:
    national = national_hourly(cfg)
    snapshots = national.index
    demand = build_demand(national)
    res = balance_residual(national)
    log.info("data balance residual: mean %.1f MW, max abs %.1f MW", res.mean(), res.abs().max())

    n = pypsa.Network()
    n.set_snapshots(snapshots)
    n.add("Carrier", ["AC", "load_shedding"])
    n.add("Bus", "DK", carrier="AC")
    n.add("Load", "demand", bus="DK", p_set=demand)

    renewables = build_renewables(cfg, national)
    for carrier, r in renewables.items():
        n.add("Carrier", carrier)
        n.add("Generator", carrier, bus="DK", carrier=carrier, p_nom=r["p_nom"],
              p_max_pu=r["p_max_pu"], marginal_cost=0.0)

    fleet = load_fleet()
    n.add("Carrier", fleet["fuel"].unique())
    avail = availability(fleet, snapshots)
    costs = marginal_costs(cfg, fleet, snapshots)
    p_min = must_run(cfg, fleet, avail, national["thermal"], demand)
    for group, row in fleet.iterrows():
        n.add("Generator", group, bus="DK", carrier=row["fuel"], p_nom=row["p_nom_mw"],
              p_max_pu=avail[group], p_min_pu=p_min[group], marginal_cost=costs[group],
              efficiency=row["efficiency"])

    n.add("Generator", "load_shedding", bus="DK", carrier="load_shedding",
          p_nom=float(demand.max()), marginal_cost=cfg["voll_eur_per_mwh"])

    inputs = {"national": national, "demand": demand, "fleet": fleet,
              "costs": costs, "must_run_mw": p_min * fleet["p_nom_mw"]}
    return n, inputs


def summarise(cfg: dict, n: pypsa.Network, inputs: dict) -> tuple[pd.Series, pd.DataFrame]:
    price = n.buses_t.marginal_price["DK"].rename("model")
    actual = actual_prices(cfg)["DK"].reindex(price.index).rename("actual")
    gen = n.generators_t.p
    wind = gen["onshore"] + gen["offshore"]
    avail_vre = n.generators_t.p_max_pu[["onshore", "offshore", "solar"]] * n.generators.p_nom[["onshore", "offshore", "solar"]]
    curtailed = avail_vre.sum(axis=1) - gen[["onshore", "offshore", "solar"]].sum(axis=1)

    fleet = inputs["fleet"]
    fuel_use = gen[fleet.index] / fleet["efficiency"]
    ef = fleet["fuel"].map(cfg["emission_factors"])
    co2 = (fuel_use * ef).sum().sum()

    s = pd.Series({
        "model_avg_price_eur_mwh": price.mean(),
        "actual_avg_price_eur_mwh": actual.mean(),
        "price_mae_eur_mwh": (price - actual).abs().mean(),
        "price_correlation": price.corr(actual),
        "model_hours_price_le_0": int((price <= 0.01).sum()),
        "actual_hours_price_le_0": int((actual <= 0).sum()),
        "demand_twh": inputs["demand"].sum() / 1e6,
        "wind_twh": wind.sum() / 1e6,
        "solar_twh": gen["solar"].sum() / 1e6,
        "thermal_twh": gen[fleet.index].sum().sum() / 1e6,
        "actual_thermal_twh": inputs["national"]["thermal"].sum() / 1e6,
        "curtailment_twh": curtailed.sum() / 1e6,
        "curtailment_pct_of_available": 100 * curtailed.sum() / avail_vre.sum().sum(),
        "wind_capture_price_eur_mwh": (wind * price).sum() / wind.sum(),
        "solar_capture_price_eur_mwh": (gen["solar"] * price).sum() / gen["solar"].sum(),
        "load_shedding_mwh": gen["load_shedding"].sum(),
        "co2_mt": co2 / 1e6,
    })

    local = price.index.tz_localize("UTC").tz_convert("Europe/Copenhagen").month
    monthly = pd.DataFrame({
        "model_price": price.groupby(local).mean(),
        "actual_price": actual.groupby(local).mean(),
        "model_thermal_gwh": gen[fleet.index].sum(axis=1).groupby(local).sum() / 1e3,
        "actual_thermal_gwh": inputs["national"]["thermal"].groupby(local).sum() / 1e3,
    }).rename_axis("month")
    return s, monthly


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--wind-scale", type=float, help="multiply onshore and offshore wind capacity")
    p.add_argument("--name", help="scenario name (results folder)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("linopy").setLevel(logging.WARNING)
    logging.getLogger("pypsa").setLevel(logging.WARNING)
    logging.getLogger("linopy").setLevel(logging.ERROR)

    cfg = load_config()
    if args.wind_scale is not None:
        cfg["scenario"]["wind_scale"] = {"onshore": args.wind_scale, "offshore": args.wind_scale}
        cfg["scenario"]["name"] = f"wind_x{args.wind_scale:g}"
    if args.name:
        cfg["scenario"]["name"] = args.name

    n, inputs = build_network(cfg)
    status, condition = n.optimize(solver_name=cfg["solver"]["name"],
                                   solver_options=cfg["solver"]["options"],
                                   include_objective_constant=False)
    if status != "ok":
        raise RuntimeError(f"optimisation failed: {status} / {condition}")

    out = ROOT / cfg["paths"]["results"] / cfg["scenario"]["name"]
    out.mkdir(parents=True, exist_ok=True)
    summary, monthly = summarise(cfg, n, inputs)
    hourly = pd.concat([n.buses_t.marginal_price["DK"].rename("model_price"),
                        actual_prices(cfg)["DK"].rename("actual_price"),
                        n.generators_t.p.add_prefix("p_")], axis=1).loc[n.snapshots]
    hourly.to_csv(out / "hourly.csv")
    monthly.to_csv(out / "monthly.csv")
    summary.to_csv(out / "summary.csv", header=["value"])
    n.export_to_netcdf(out / "network.nc")

    log.info("\nScenario: %s\n%s\n\n%s", cfg["scenario"]["name"],
             summary.round(2).to_string(), monthly.round(1).to_string())


if __name__ == "__main__":
    main()
