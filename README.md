# PyPSA Denmark

Model of the Danish electricity system for 2025, built with
[PyPSA](https://pypsa.org). It estimates the hourly marginal electricity price
from the cost of the plants that run each hour.

Planned steps:

1. **Baseline 2025** (this version): one node for all of Denmark, hourly, net
   imports fixed at their actual values, combined heat and power (CHP) plants
   held on by heat demand (must-run).
2. **More wind**: scale wind capacity up with the same 2025 weather.
3. **Interconnection**: replace the fixed imports with links to neighbouring
   bidding zones.

## Run it

```bash
pip install -r requirements.txt
```

```bash
python data/download.py
```

```bash
python main.py
```

```bash
python main.py --wind-scale 2
```

Results go to `results/<scenario>/`: `summary.csv`, `monthly.csv`,
`hourly.csv` (prices and dispatch) and `network.nc` (the solved PyPSA network).

## Layout

| Path | Contents |
|---|---|
| `config/config.yaml` | Year, scenario, fuel and CO₂ prices, must-run settings |
| `data/download.py` | Downloads raw data from Energinet's Energi Data Service |
| `data/settlement.py` | Sums DK1 + DK2 settlement data into national hourly series |
| `demand/demand.py` | Demand the Danish plants must cover (consumption − net imports) |
| `production/renewables.py` | Wind and solar capacity and hourly availability |
| `production/thermal_fleet.csv` | Thermal plants, grouped by fuel and size |
| `production/thermal.py` | Marginal costs and CHP must-run |
| `validation/prices.py` | Actual 2025 day-ahead prices for comparison |
| `main.py` | Builds, solves and summarises the model |

## Data sources

From [Energi Data Service](https://www.energidataservice.dk) (Energinet), all 2025:

- `ProductionConsumptionSettlement`: hourly production by type, consumption and
  exchange per border, DK1 and DK2
- `CapacityPerMunicipality`: monthly installed wind, solar and thermal capacity
- `GasDailyBalancingPrice`: daily Danish gas price (EEX spot index)
- `Elspotprices` (Jan–Sep, hourly) and `DayAheadPrices` (Oct–Dec, 15-minute):
  actual day-ahead prices, used only for validation

Assumptions not taken from a dataset are marked `ASSUMPTION` in
`config/config.yaml` and `production/thermal_fleet.csv`: coal, biomass, waste
and oil prices, monthly CO₂ prices, plant efficiencies, how the thermal fleet
splits into groups, and which large unit closed on 1 April 2025. Group totals
match Energinet's thermal capacity (3,722 MW in units ≥100 MW until March,
3,072 MW after; 2,395 MW in smaller units).

## Method notes

- **Demand** = gross consumption − net imports − small hydro. Gross consumption
  includes grid losses, power-to-heat and self-consumed production.
- **Wind and solar availability** = actual 2025 output ÷ installed capacity.
  The model may curtail below it.
- **Thermal marginal cost** = (fuel + CO₂ × emission factor) ÷ efficiency +
  variable O&M. Gas follows the daily Danish gas price.
- **Must-run**: each month, the thermal plants must produce at least the 5th
  percentile of their actual output that month. Waste plants take the first
  share, the other CHP groups share the rest by capacity.
- **Load shedding** at 3,000 €/MWh keeps the model solvable.

## Baseline results (2025)

| | Model | Actual |
|---|---|---|
| Average price (€/MWh) | 79.8 | 81.6 |
| Hours at or below zero | 937 | 350 |
| Thermal generation (TWh) | 9.49 | 9.45 |

The annual average is close, but the hourly match is weak (correlation 0.33,
mean absolute error 35 €/MWh). The model price stays between about 85 and
96 €/MWh in most hours, set by coal (Nordjyllandsværket) or biomass CHP. With
imports fixed, Danish coal and biomass plants are enough to cover every hour,
so gas never sets the price. In reality hourly prices follow Germany, Norway
and Sweden through the interconnectors, which step 3 will model.
