"""Power market analysis of the 2025 baseline: dispatch, prices and trends.

Run after the model:
    python main.py
    python data_analysis/analysis.py            # baseline
    python data_analysis/analysis.py wind_x2    # any other scenario folder

Figures go to data_analysis/figures/<scenario>/, key numbers to
data_analysis/figures/<scenario>/key_figures.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_config  # noqa: E402
from data.settlement import national_hourly  # noqa: E402
from production.renewables import capacity_factors, installed_capacity_hourly  # noqa: E402
from production.thermal import load_fleet, marginal_costs  # noqa: E402

# ---- style -----------------------------------------------------------------
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
ACTUAL, MODEL = "#2a78d6", "#eb6834"  # categorical slots 1 and 2

# Stack order bottom -> top; colours validated as an adjacent sequence
# (colour-blind separation >= 8 between neighbours).
TECH = {
    "Waste": "#e87ba4",
    "Biomass": "#008300",
    "Coal": "#6250d6",
    "Gas & oil": "#eb6834",
    "Onshore wind": "#1baf7a",
    "Offshore wind": "#2a78d6",
    "Solar": "#eda100",
}
GROUPS = {
    "Waste": ["waste_chp"],
    "Biomass": ["biomass_large", "biomass_small"],
    "Coal": ["coal_njv3", "coal_fv7"],
    "Gas & oil": ["gas_large", "oil_gas_reserve", "large_closed_q1", "gas_small"],
    "Onshore wind": ["onshore"],
    "Offshore wind": ["offshore"],
    "Solar": ["solar"],
}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 9, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "legend.frameon": False, "legend.fontsize": 8, "lines.linewidth": 2,
})
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def save(fig, out: Path, name: str) -> None:
    fig.savefig(out / f"{name}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.png")


# ---- data ------------------------------------------------------------------
def load(scenario: str):
    cfg = load_config()
    hourly = pd.read_csv(ROOT / cfg["paths"]["results"] / scenario / "hourly.csv",
                         index_col=0, parse_dates=True)
    national = national_hourly(cfg)
    fleet = load_fleet()
    costs = marginal_costs(cfg, fleet, national.index)
    cf = capacity_factors(cfg, national)
    cap = installed_capacity_hourly(cfg, national.index)

    local = hourly.index.tz_localize("UTC").tz_convert("Europe/Copenhagen").tz_localize(None)
    for df in (hourly, national, costs, cf, cap):
        df.index = local

    gen = pd.DataFrame({tech: hourly[[f"p_{g}" for g in gens]].sum(axis=1)
                        for tech, gens in GROUPS.items()})
    return cfg, hourly, national, gen, fleet, costs, cf, cap


# ---- figures ---------------------------------------------------------------
def dispatch_week(out, hourly, national, gen, start: str, name: str, title: str) -> None:
    sl = slice(start, pd.Timestamp(start) + pd.Timedelta(days=7) - pd.Timedelta(hours=1))
    g, nat, h = gen.loc[sl], national.loc[sl], hourly.loc[sl]
    fig, (ax, axp) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.12})
    ax.stackplot(g.index, g.T.values, labels=g.columns, colors=list(TECH.values()),
                 edgecolor=SURFACE, linewidth=0.6)
    imp = nat["net_import"]
    ax.fill_between(imp.index, 0, imp.clip(upper=0), color=MUTED, alpha=0.35,
                    linewidth=0, label="Net exports (fixed)")
    ax.plot(nat.index, nat["consumption"], color=INK, linewidth=1.6, label="Consumption")
    ax.plot(nat.index, nat["consumption"] - imp, color=INK, linewidth=1.2, linestyle="--",
            label="Demand on Danish plants\n(consumption − net imports)")
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.set_ylabel("MW")
    ax.set_title(title)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper left", bbox_to_anchor=(1.01, 1))

    axp.plot(h.index, h["actual_price"], color=ACTUAL, label="Actual price")
    axp.plot(h.index, h["model_price"], color=MODEL, label="Model price")
    axp.set_ylabel("€/MWh")
    axp.set_title("Price", fontsize=10)
    axp.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    axp.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%a %d %b"))
    save(fig, out, name)


def monthly_mix(out, gen, national) -> None:
    m = gen.groupby(gen.index.month).sum() / 1e3  # GWh
    imp = national["net_import"].groupby(national.index.month).sum() / 1e3
    fig, ax = plt.subplots(figsize=(11, 4.8))
    bottom = np.zeros(12)
    x = np.arange(12)
    for tech, color in TECH.items():
        ax.bar(x, m[tech].values, bottom=bottom, color=color, width=0.7, label=tech,
               edgecolor=SURFACE, linewidth=0.8)
        bottom += m[tech].values
    ax.bar(x, imp.values, bottom=bottom, color=MUTED, alpha=0.35, width=0.7,
           label="Net imports (actual)", edgecolor=SURFACE, linewidth=0.8)
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel("GWh")
    ax.set_title("Monthly electricity supply, 2025 (model dispatch + actual net imports)")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper left", bbox_to_anchor=(1.01, 1))
    save(fig, out, "02_monthly_supply_mix")


def monthly_prices(out, hourly) -> None:
    m = hourly.groupby(hourly.index.month)[["actual_price", "model_price"]].mean()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(MONTHS, m["actual_price"], color=ACTUAL, marker="o", markersize=5, label="Actual")
    ax.plot(MONTHS, m["model_price"], color=MODEL, marker="o", markersize=5, label="Model")
    for col, color in (("actual_price", ACTUAL), ("model_price", MODEL)):
        ax.annotate(f"{m[col].iloc[-1]:.0f}", (11, m[col].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", color=INK2, fontsize=8)
    ax.set_ylim(0, None)
    ax.set_ylabel("€/MWh")
    ax.set_title("Average monthly day-ahead price, Denmark 2025")
    ax.legend(loc="lower left")
    save(fig, out, "03_monthly_prices")


def duration_curve(out, hourly) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    hours = np.arange(1, len(hourly) + 1)
    for col, color, label in (("actual_price", ACTUAL, "Actual"), ("model_price", MODEL, "Model")):
        ax.plot(hours, np.sort(hourly[col].values)[::-1], color=color, label=label)
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.set_xlim(0, len(hourly))
    ax.set_ylim(-60, 400)
    ax.set_xlabel("Hours of the year, sorted from highest to lowest price")
    ax.set_ylabel("€/MWh")
    ax.set_title("Price duration curve, 2025 (y-axis cut at 400 €/MWh)")
    ax.legend(loc="upper right")
    save(fig, out, "04_price_duration_curve")


def daily_profile(out, hourly) -> None:
    seasons = {"Winter (Dec–Feb)": [12, 1, 2], "Spring (Mar–May)": [3, 4, 5],
               "Summer (Jun–Aug)": [6, 7, 8], "Autumn (Sep–Nov)": [9, 10, 11]}
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.6), sharey=True)
    for ax, (name, months) in zip(axes, seasons.items()):
        s = hourly[hourly.index.month.isin(months)]
        p = s.groupby(s.index.hour)[["actual_price", "model_price"]].mean()
        ax.plot(p.index, p["actual_price"], color=ACTUAL, label="Actual")
        ax.plot(p.index, p["model_price"], color=MODEL, label="Model")
        ax.set_title(name, fontsize=10)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xlabel("Hour (Danish time)")
    axes[0].set_ylabel("€/MWh")
    axes[0].set_ylim(0, None)
    axes[-1].legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    fig.suptitle("Average price by hour of day", x=0.01, ha="left", fontweight="bold", fontsize=11)
    save(fig, out, "05_daily_price_profile")


def merit_order(out, fleet, costs) -> None:
    mc = costs.mean().sort_values()
    cap = fleet.loc[mc.index, "p_nom_mw"]
    tech_of = {g: t for t, gs in GROUPS.items() for g in gs}
    left = np.concatenate([[0], cap.cumsum().values[:-1]])
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for (g, c), x0, w in zip(mc.items(), left, cap.values):
        ax.bar(x0, c, width=w, align="edge", color=TECH[tech_of[g]], edgecolor=SURFACE, linewidth=1.5)
        ax.text(x0 + w / 2, max(c, 0) + 6, g.replace("_", " "), ha="center", va="bottom",
                fontsize=7, color=INK2, rotation=90)
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.set_xlim(0, cap.sum())
    ax.set_ylim(min(mc.min() - 10, 0), mc.max() + 70)
    ax.set_xlabel("Cumulative thermal capacity (MW)")
    ax.set_ylabel("€/MWh")
    ax.set_title("Thermal merit order (2025 average marginal cost)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=TECH[t]) for t in ("Waste", "Biomass", "Coal", "Gas & oil")]
    ax.legend(handles, ["Waste", "Biomass", "Coal", "Gas & oil"], loc="upper left")
    save(fig, out, "06_merit_order")


def price_setters(out, hourly, costs) -> pd.Series:
    price = hourly["model_price"]
    tech_of = {g: t for t, gs in GROUPS.items() for g in gs}
    setter = pd.Series("Wind/solar surplus (price ≈ 0)", index=price.index)
    for g in costs.columns:
        setter[(costs[g] - price).abs() < 0.01] = tech_of[g]
    setter[price >= 2999] = "Load shedding"
    share = setter.value_counts()
    fig, ax = plt.subplots(figsize=(8, 3.2))
    colors = [TECH.get(t, MUTED) for t in share.index]
    ax.barh(share.index[::-1], share.values[::-1], color=colors[::-1], height=0.6)
    for i, v in enumerate(share.values[::-1]):
        ax.text(v + 60, i, f"{v:,} h ({100 * v / len(price):.0f}%)", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, share.max() * 1.3)
    ax.set_xlabel("Hours in 2025")
    ax.grid(axis="y", visible=False)
    ax.set_title("Which technology sets the model price")
    save(fig, out, "07_price_setting_technology")
    return share


def price_vs_residual(out, hourly, national) -> None:
    vre = national[["onshore", "offshore", "solar"]].sum(axis=1)
    residual = (national["consumption"] - vre) / 1e3
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, col, color, name in ((axes[0], "actual_price", ACTUAL, "Actual"),
                                 (axes[1], "model_price", MODEL, "Model")):
        ax.scatter(residual, hourly[col], s=3, color=color, alpha=0.25, linewidths=0)
        ax.axhline(0, color=AXIS, linewidth=0.8)
        ax.axvline(0, color=AXIS, linewidth=0.8)
        ax.set_title(f"{name} price", fontsize=10)
        ax.set_xlabel("Residual load: consumption − wind − solar (GW)")
    axes[0].set_ylabel("€/MWh")
    axes[0].set_ylim(-60, 350)
    fig.suptitle("Price against residual load (each dot = one hour)", x=0.01, ha="left",
                 fontweight="bold", fontsize=11)
    save(fig, out, "08_price_vs_residual_load")


def imports_vs_wind(out, national) -> None:
    vre = national[["onshore", "offshore", "solar"]].sum(axis=1) / 1e3
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.scatter(vre, national["net_import"] / 1e3, s=3, color=ACTUAL, alpha=0.25, linewidths=0)
    fit = np.polyfit(vre, national["net_import"] / 1e3, 1)
    xs = np.linspace(vre.min(), vre.max(), 2)
    ax.plot(xs, np.polyval(fit, xs), color=INK, linewidth=1.4)
    ax.annotate(f"slope {fit[0]:.2f}: each extra GW of wind/solar\n≈ {-fit[0]:.2f} GW less import",
                (xs[1], np.polyval(fit, xs[1])), xytext=(-10, 30), textcoords="offset points",
                ha="right", fontsize=8, color=INK2)
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.set_xlabel("Wind + solar output (GW)")
    ax.set_ylabel("Net imports (GW, negative = export)")
    ax.set_title("Interconnectors absorb wind variability (actual 2025)")
    save(fig, out, "09_net_imports_vs_wind")


def capture_prices(out, hourly, national) -> pd.DataFrame:
    p = hourly["actual_price"]
    rows = {}
    for name, cols in (("Wind", ["onshore", "offshore"]), ("Solar", ["solar"])):
        q = national[cols].sum(axis=1)
        rows[name] = (q * p).groupby(p.index.month).sum() / q.groupby(p.index.month).sum()
    rows["Average price"] = p.groupby(p.index.month).mean()
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(MONTHS, df["Average price"], color=INK2, linestyle="--", linewidth=1.4, label="Average price")
    ax.plot(MONTHS, df["Wind"], color="#1baf7a", marker="o", markersize=5, label="Wind capture price")
    ax.plot(MONTHS, df["Solar"], color="#eda100", marker="o", markersize=5, label="Solar capture price")
    ax.set_ylim(0, None)
    ax.set_ylabel("€/MWh")
    ax.set_title("What wind and solar actually earned per MWh (actual 2025 prices)")
    ax.legend(loc="lower left")
    save(fig, out, "10_capture_prices")
    return df


VRE = {"onshore": ("Onshore wind", "#1baf7a"), "offshore": ("Offshore wind", "#2a78d6"),
       "solar": ("Solar", "#eda100")}
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def renewable_output(out, national, cap) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True, gridspec_kw={"hspace": 0.3})
    for ax, (key, (name, color)) in zip(axes, VRE.items()):
        daily = national[key].resample("D").mean()
        ax.fill_between(national.index, 0, national[key], color=color, alpha=0.18, linewidth=0,
                        label="Hourly output")
        ax.plot(daily.index + pd.Timedelta(hours=12), daily, color=color, linewidth=1.6,
                label="Daily average")
        ax.plot(cap.index, cap[key], color=INK2, linestyle="--", linewidth=1.2,
                label="Installed capacity")
        ax.set_title(f"{name}: {national[key].sum() / 1e6:.1f} TWh, installed "
                     f"{cap[key].iloc[-1]:,.0f} MW at year end", fontsize=10)
        ax.set_ylabel("MW")
        ax.set_ylim(0, None)
    axes[0].legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    axes[-1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    fig.suptitle("Wind and solar output, 2025 (Energinet measured data)", x=0.01, ha="left",
                 fontweight="bold", fontsize=11, y=0.95)
    save(fig, out, "11_wind_solar_output")


def capacity_factor_heatmaps(out, cf) -> pd.DataFrame:
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    for ax, (key, (name, _)) in zip(axes, VRE.items()):
        grid = cf[key].groupby([cf.index.month, cf.index.hour]).mean().unstack() * 100
        im = ax.imshow(grid.values, aspect="auto", cmap=cmap, vmin=0, vmax=70, origin="upper")
        ax.set_title(f"{name} (year {cf[key].mean() * 100:.0f}%)", fontsize=10)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xlabel("Hour of day (Danish time)")
        ax.grid(False)
    axes[0].set_yticks(range(12), MONTHS)
    cbar = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02)
    cbar.set_label("Average capacity factor (%)", color=INK2)
    cbar.outline.set_visible(False)
    fig.suptitle("Capacity factor by month and hour of day, 2025", x=0.01, ha="left",
                 fontweight="bold", fontsize=11, y=1.0)
    save(fig, out, "12_capacity_factor_heatmaps")
    monthly = cf.groupby(cf.index.month).mean() * 100
    monthly.index = MONTHS
    return monthly


def capacity_factor_duration(out, cf) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    hours = np.arange(1, len(cf) + 1)
    for key, (name, color) in VRE.items():
        ax.plot(hours, np.sort(cf[key].values)[::-1] * 100, color=color, label=name)
    ax.set_xlim(0, len(cf))
    ax.set_ylim(0, 100)
    ax.set_xlabel("Hours of the year, sorted from highest to lowest output")
    ax.set_ylabel("Capacity factor (%)")
    ax.set_title("Capacity factor duration curves, 2025")
    ax.legend(loc="upper right")
    save(fig, out, "13_capacity_factor_duration")


# ---- main ------------------------------------------------------------------
def main(scenario: str = "baseline") -> None:
    cfg, hourly, national, gen, fleet, costs, cf, cap = load(scenario)
    out = Path(__file__).with_name("figures") / scenario
    out.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {out.relative_to(ROOT)}")

    dispatch_week(out, hourly, national, gen, "2025-01-13", "01a_dispatch_winter_week",
                  "Dispatch, winter week (13–19 Jan 2025)")
    dispatch_week(out, hourly, national, gen, "2025-06-16", "01b_dispatch_summer_week",
                  "Dispatch, summer week (16–22 Jun 2025)")
    monthly_mix(out, gen, national)
    monthly_prices(out, hourly)
    duration_curve(out, hourly)
    daily_profile(out, hourly)
    merit_order(out, fleet, costs)
    share = price_setters(out, hourly, costs)
    price_vs_residual(out, hourly, national)
    imports_vs_wind(out, national)
    capture = capture_prices(out, hourly, national)
    renewable_output(out, national, cap)
    cf_monthly = capacity_factor_heatmaps(out, cf)
    capacity_factor_duration(out, cf)
    cf_monthly.round(1).to_csv(out / "capacity_factors_monthly.csv")
    profiles = pd.concat([national[list(VRE)].add_suffix("_mw"), cap.add_suffix("_capacity_mw"),
                          cf.add_suffix("_capacity_factor")], axis=1).round(4)
    profiles.index.name = "time_danish"
    profiles.to_csv(out / "wind_solar_profiles.csv")
    print("\nMonthly capacity factors (%):\n" + cf_monthly.round(1).to_string())

    p_act, p_mod = hourly["actual_price"], hourly["model_price"]
    vre = national[["onshore", "offshore", "solar"]].sum(axis=1)
    wind = national[["onshore", "offshore"]].sum(axis=1)
    total = national["consumption"].sum()
    figs = pd.Series({
        "consumption_twh": total / 1e6,
        "wind_share_of_consumption_pct": 100 * wind.sum() / total,
        "solar_share_of_consumption_pct": 100 * national["solar"].sum() / total,
        "thermal_share_of_consumption_pct": 100 * national["thermal"].sum() / total,
        "net_import_share_of_consumption_pct": 100 * national["net_import"].sum() / total,
        "hours_vre_exceeds_consumption": int((vre > national["consumption"]).sum()),
        "hours_net_export": int((national["net_import"] < 0).sum()),
        "actual_avg_price": p_act.mean(),
        "model_avg_price": p_mod.mean(),
        "actual_price_std": p_act.std(),
        "model_price_std": p_mod.std(),
        "actual_max_price": p_act.max(),
        "actual_min_price": p_act.min(),
        "actual_hours_negative": int((p_act < 0).sum()),
        "actual_wind_capture_price": (wind * p_act).sum() / wind.sum(),
        "actual_solar_capture_price": (national["solar"] * p_act).sum() / national["solar"].sum(),
        "corr_actual_price_vs_wind": p_act.corr(wind),
        "corr_net_import_vs_wind": national["net_import"].corr(wind),
        **{f"model_price_set_by_{k}_hours": v for k, v in share.items()},
    })
    figs.to_csv(out / "key_figures.csv", header=["value"])
    capture.to_csv(out / "capture_prices_monthly.csv")
    print("\n" + figs.round(2).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:2])
