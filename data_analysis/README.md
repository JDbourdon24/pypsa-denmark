# Danish power market analysis, 2025

How Denmark's electricity was supplied and priced in 2025, and how well the
baseline model (one node, net imports fixed) reproduces it.

Regenerate everything with:

```bash
python main.py
```

```bash
python data_analysis/analysis.py
```

Figures are in [`figures/baseline/`](figures/baseline/). Key numbers are in
[`figures/baseline/key_figures.csv`](figures/baseline/key_figures.csv).

## 2025 at a glance (actual data)

| | 2025 |
|---|---|
| Electricity consumption | 40.5 TWh |
| Wind | 47% of consumption |
| Solar | 11% |
| Danish thermal plants | 23% |
| Net imports | 18% |
| Hours where wind + solar exceeded consumption | 871 |
| Hours Denmark was a net exporter | 2,307 |
| Average day-ahead price | 81.6 €/MWh |
| Price range | −30.6 to 583.4 €/MWh |
| Hours with negative prices | 341 |
| Wind capture price (what wind earned per MWh) | 69.0 €/MWh, 85% of average |
| Solar capture price | 51.0 €/MWh, 62% of average |

## 0. Wind and solar production: how it is calculated

Wind and solar are **not simulated from weather data**. The model uses what
actually happened in 2025:

1. **Hourly output:** measured production from Energinet's
   `ProductionConsumptionSettlement` dataset, summed over DK1 and DK2:
   - onshore wind = `OnshoreWindLt50kW_MWh` + `OnshoreWindGe50kW_MWh`
   - offshore wind = `OffshoreWindLt100MW_MWh` + `OffshoreWindGe100MW_MWh`
   - solar = the three `SolarPower…` size classes + `SolarPowerSelfConMWh`
     (rooftop solar consumed on site)
2. **Installed capacity:** Energinet's `CapacityPerMunicipality`, monthly,
   summed over all municipalities.
3. **Capacity factor** = hourly output ÷ capacity installed that month.
4. **In the model** (`production/renewables.py`), each technology has a capacity
   equal to its year-end value × the scenario's scale factor. Its hourly
   availability is actual output ÷ year-end capacity. With a scale factor of 1,
   the model can produce exactly the 2025 output and may curtail below it. With
   `--wind-scale 2`, the same hourly profile is doubled.

The hourly profiles are exported to
[`figures/baseline/wind_solar_profiles.csv`](figures/baseline/wind_solar_profiles.csv)
(output in MW, installed capacity and capacity factor, Danish time).

![Wind and solar output](figures/baseline/11_wind_solar_output.png)

| 2025 | Output | Year-end capacity | Capacity factor |
|---|---|---|---|
| Onshore wind | 9.8 TWh | 4,878 MW | 23% |
| Offshore wind | 9.3 TWh | 2,648 MW | 40% |
| Solar | 4.5 TWh | 4,956 MW (up from 4,150 in January) | 11% |

![Capacity factor heatmaps](figures/baseline/12_capacity_factor_heatmaps.png)

- **Wind is a winter resource.** Offshore runs at 51–55% capacity factor from
  October to January, against 22–30% in April, July and August. Onshore
  follows the same pattern at lower levels.
- **Solar is the mirror image:** 16–20% from April to August, under 3% from
  November to January, all within roughly 07:00–19:00.
- **The offshore midday dip from March to August is not weather.** Offshore
  wind farms stop producing when prices go negative, which happens around
  midday when solar floods the market. The profiles are therefore *measured
  output after real-world curtailment*, not the full wind available. This
  slightly understates offshore potential, which matters for the wind-scaling
  scenarios. A weather-based profile (e.g. ERA5 / renewables.ninja) would fix
  it.

![Capacity factor duration curves](figures/baseline/13_capacity_factor_duration.png)

- Offshore wind produces above 50% of capacity in about 3,170 hours a year;
  onshore only about 980.
- Solar produces almost nothing (under 1% of capacity) in 52% of the hours of the year, mostly night.

Monthly capacity factors (%):

| | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onshore | 30.8 | 22.2 | 26.0 | 13.4 | 21.1 | 26.0 | 14.7 | 16.9 | 22.3 | 27.0 | 25.5 | 29.4 |
| Offshore | 52.3 | 42.1 | 38.4 | 21.5 | 32.3 | 37.5 | 27.6 | 30.2 | 40.9 | 51.3 | 51.3 | 54.6 |
| Solar | 2.0 | 5.3 | 12.9 | 16.3 | 20.3 | 19.4 | 18.4 | 17.5 | 13.3 | 6.5 | 2.7 | 1.6 |

## 1. Dispatch

![Winter week](figures/baseline/01a_dispatch_winter_week.png)

![Summer week](figures/baseline/01b_dispatch_summer_week.png)

- **Wind sets the rhythm.** In the winter week, wind covers almost all demand
  on the 13th and 14th. Denmark exports the surplus (grey area below zero),
  and the actual price falls to about 15 €/MWh.
- **When wind drops, imports and thermal plants fill the gap.** On 15 January
  wind fell sharply and the actual price spiked above 300 €/MWh. The model
  stays at about 95 €/MWh, because its imports are fixed at what actually
  happened, so it never sees the scarcity that drove the real price.
- **Waste and biomass CHP plants run all the time** (must-run), even in summer.

![Monthly supply mix](figures/baseline/02_monthly_supply_mix.png)

- Thermal output is concentrated in winter (heat demand). From May to August
  it is almost only waste plants plus a little coal and biomass.
- Solar is a summer resource (April–September). Wind is strongest from
  October to March.
- Denmark is a net importer in every month. Imports are largest in April, July
  and August, when wind is weaker and thermal plants are mostly off.

## 2. Prices

![Monthly prices](figures/baseline/03_monthly_prices.png)

- The model matches the yearly average well (79.8 against 81.6 €/MWh) and
  follows the seasonal pattern: higher in winter, lower in late spring.
- It misses the extremes. It underestimates January and February (cold spells,
  high gas prices abroad) and overestimates May and June (cheap solar and
  Nordic hydro imports).

![Price duration curve](figures/baseline/04_price_duration_curve.png)

- The real price is spread out: 151 hours above 200 €/MWh and a long
  tail towards zero.
- The model price is almost flat at 85–96 €/MWh, then drops straight to zero
  for about 930 hours. **This is the main limitation of the isolated model.**

![Daily profile](figures/baseline/05_daily_price_profile.png)

- Real prices have a strong daily shape. In spring and summer there is a deep
  midday dip, because solar pushes the price down to about 20 €/MWh. There
  are morning and evening peaks of 110–145 €/MWh, highest in winter and autumn.
- The model shows almost none of this. With imports fixed, solar mainly
  displaces imports in reality, while in the model it only shaves a little
  off a flat thermal price.

## 3. Why the model price is flat

![Merit order](figures/baseline/06_merit_order.png)

- In the model's merit order (cheapest plants first), the first ~3,500 MW is
  waste, small biomass, coal and large biomass, all between 85 and
  96 €/MWh. Gas only starts at about 120 €/MWh.
- After fixing net imports, Danish plants never need to supply more than about
  3.3 GW. **Gas is therefore never the price-setting plant.**

![Price setter](figures/baseline/07_price_setting_technology.png)

- Coal sets the model price 46% of the time, biomass 43%. In 11% of hours there
  is surplus wind/solar and the price is about zero.

![Price vs residual load](figures/baseline/08_price_vs_residual_load.png)

- **Actual:** the higher the residual load (consumption minus wind and solar),
  the higher the price, with spikes above 4 GW. Below zero residual load,
  prices fall towards zero.
- **Model:** two flat bands, about 90 €/MWh or zero, almost regardless of
  residual load.

## 4. The role of interconnectors

![Imports vs wind](figures/baseline/09_net_imports_vs_wind.png)

- Net imports and wind/solar output are strongly linked (correlation −0.89).
  On average, each extra GW of wind and solar means about 0.68 GW less import
  or more export.
- **The interconnectors are Denmark's main source of flexibility.** They are
  what links Danish prices to Germany, Norway and Sweden, and why an isolated
  model cannot reproduce hourly prices.

## 5. What wind and solar earn

![Capture prices](figures/baseline/10_capture_prices.png)

- Wind earned 69 €/MWh on average, 15% below the average price. Wind tends to
  blow at the same time across the region, which pushes prices down when it
  produces most.
- Solar is hit harder: 51 €/MWh, 38% below average, and around or under 40 €/MWh
  from April to June, when midday prices collapse.
- This gap (the "cannibalisation" effect) is what the wind-scaling scenarios
  will measure: it should grow as wind capacity grows.

## Conclusions

1. The baseline gets energy volumes right. Thermal output matches actual
   within 0.4%, and the annual average price is within 2 €/MWh.
2. It does not capture hourly price dynamics (correlation 0.33), because
   Danish prices are set by the coupled European market, not by Danish plants
   alone.
3. Scaling up wind with the current setup will mainly show more zero-price
   hours and more wasted wind (curtailment). Adding interconnectors (step 3)
   is needed to see how much of that surplus can be exported, and at what
   price.
