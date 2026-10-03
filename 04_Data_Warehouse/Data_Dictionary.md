# PULSE_DW — Data Dictionary

Schema `dw`. Money in INR, distances in km, durations in minutes, timestamps in
local Bengaluru time. `time_key` = yyyymmddhh of the hour an event **started**.
KPI formulas built on these columns: `01_Business_Understanding/KPI_Dictionary.md`.

## Dimensions

**Dim_Time** — `time_key` PK · `date_value` · `hour_of_day` (0–23) · `day_of_week` (1 = Mon) ·
`day_name` · `week_number` (1 = first simulated week) · `is_weekend` · `is_peak_hour`
(weekday 08–10, 17–20) · `is_rain_day` · `is_event_day` · `data_split`
(`history` / `holdout` / `spill`).

**Dim_Zone** — `zone_key` PK · `zone_code` (e.g. `WHF`) · `zone_name` · `zone_type`
(office, residential, mixed, restaurant_cluster, transit_hub) · `latitude`,
`longitude` (approximate centroid) · `city`.

**Dim_Service** — `service_key` PK (1 mobility, 2 food) · `service_code` · `service_name`.

**Dim_Vehicle** — `vehicle_key` PK (1 two-wheeler, 2 four-wheeler) · `vehicle_code` ·
`vehicle_name` · `can_mobility` · `can_food`.

**Dim_Driver** — `driver_key` PK · `partner_code` · `vehicle_key` FK · `home_zone_key` FK ·
`shift_type` (morning, split, evening, full_day, night).

**Dim_Customer** — `customer_key` PK · `customer_code` · `home_zone_key` FK.

**Dim_Restaurant** — `restaurant_key` PK · `restaurant_code` · `zone_key` FK · `cuisine`.

## Facts

**Fact_Ride_Requests** (every request) — `ride_request_key` PK · `request_code` ·
`time_key` · `customer_key` · `pickup_zone_key` · `dropoff_zone_key` · `driver_key`
(NULL if no partner) · `vehicle_key` · `request_ts` · `assigned_ts` · `request_status`
(`completed`, `cancelled_customer`, `cancelled_no_partner`) · `is_completed` ·
`requested_trip_km` · `pickup_km` · `pickup_eta_min` (request → partner arrival).

**Fact_Rides** (completed only) — `ride_key` PK · `ride_request_key` FK (unique) ·
keys as above · `pickup_ts` · `dropoff_ts` · `trip_km` · `trip_minutes` · `pickup_km` ·
`fare` · `partner_payout` · `platform_revenue` (= fare − payout).

**Fact_Food_Orders** (every order) — `order_key` PK · `order_code` · `time_key` ·
`customer_key` · `customer_zone_key` · `restaurant_key` · `restaurant_zone_key` ·
`driver_key` · `placed_ts` · `assigned_ts` · `ready_ts` · `picked_ts` · `delivered_ts` ·
`order_status` (`delivered`, `cancelled_customer`, `cancelled_no_partner`,
`cancelled_restaurant`) · `is_delivered` · `order_value` · `commission` ·
`delivery_fee` · `partner_payout` · `platform_revenue` (= commission + fee − payout,
delivered only) · `pickup_km` · `delivery_km` · `prep_minutes` (placed → ready) ·
`delivery_minutes` (placed → delivered).

**Fact_Delivery_Events** — `delivery_event_key` PK · `order_key` FK · `event_type`
(`placed` 1, `assigned` 2, `food_ready` 3, `picked_up` 4, `delivered` 5, `cancelled` 6) ·
`event_seq` · `event_ts` · `time_key` · `zone_key` (customer zone for placed/delivered/
cancelled, restaurant zone otherwise) · `driver_key`.

**Fact_Driver_Availability** — `availability_key` PK · `time_key` · `driver_key` ·
`zone_key` (partner location at the start of the hour) · `vehicle_key` ·
`online_minutes` · `busy_minutes` (on a job) · `idle_minutes` · `empty_km`
(pickup km of jobs started that hour).

**Fact_Supply_Allocation** (Phase 10) — optimizer output: `scenario_code`, `run_ts`,
`time_key`, origin/destination zone, vehicle, service, `partners`, `reposition_cost`.

**Fact_Repositioning** (Phase 10) — simulated moves: `scenario_code`, `time_key`,
`driver_key`, origin/destination zone, `reposition_km`, `reposition_minutes`,
`reposition_cost`.

**Fact_Incentives** (Phase 11) — `scenario_code`, `time_key`, `zone_key`, `service_key`,
optional `driver_key`, `incentive_type`, `incentive_amount`, `extra_partner_hours`.

## Derived tables

**Agg_Pressure_ZoneHour** (Phase 8, rebuilt by `scripts/report_phase8.py`) — one row
per zone and hour: `ride_requests`, `food_orders`, `lost_rides`, `lost_orders`,
`work_hours` (rides ÷ 2 + orders ÷ 3), `supply_hours` (partners present),
`two_wheeler_hours`, `local_mpi`, `nbhd_work_hours`, `nbhd_supply_hours`,
`nbhd_mpi` (zones within 20 minutes), `city_mpi`, `mobility_mpi`, `food_mpi`,
`pressure_state` (Under-supplied / Balanced / Over-supplied / No activity) and
`shortage_type` (Fix now / Reposition ahead / Citywide shortage / None).
Definitions: `08_Supply_Demand_Imbalance/README.md`.

**Fact_Demand_Forecast** (Phase 9) — holdout forecasts: `time_key`, `zone_key`,
`service_key`, `model_name`, `forecast_demand`, `actual_demand`.

**Fact_Supply_Forecast** (Phase 9) — partners online by home zone: `time_key`,
`zone_key`, `vehicle_key`, `model_name`, `forecast_partners`, `actual_partners`.

**Fact_Pressure_Forecast** (Phase 9) — week-ahead shortage prediction:
`forecast_work_hours`, `forecast_supply_hours`, `forecast_mpi`,
`predicted_short`, `actual_short`, `lost_jobs`. All three are rebuilt by
`scripts/report_phase9.py`; definitions in `09_Forecasting/01_Forecasting_Approach.md`.
