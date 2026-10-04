/* PULSE Phase 10 - 06: the Phase 9 week-ahead demand forecast the optimizer
   plans with (GBM calendar: no weather assumed). Holdout weeks only. */
USE PULSE_DW;

SELECT t.date_value, t.hour_of_day, z.zone_code, s.service_code, f.forecast_demand
FROM dw.Fact_Demand_Forecast f
JOIN dw.Dim_Time t    ON t.time_key = f.time_key
JOIN dw.Dim_Zone z    ON z.zone_key = f.zone_key
JOIN dw.Dim_Service s ON s.service_key = f.service_key
WHERE f.model_name = 'GBM calendar';
