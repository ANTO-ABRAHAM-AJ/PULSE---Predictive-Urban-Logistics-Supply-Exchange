/* =========================================================================
   PULSE Phase 9 - 04: forecast accuracy, computed in the warehouse
   Result Set A: demand forecast WAPE and bias by model and service
   Result Set B: baseline supply forecast WAPE and bias by model and vehicle
   Holdout weeks 13-16 only. WAPE = sum|forecast - actual| / sum(actual).
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
SELECT s.service_name                                                                    AS [Service],
       f.model_name                                                                      AS [Model],
       SUM(f.actual_demand)                                                              AS [Actual demand],
       CAST(SUM(f.forecast_demand) AS DECIMAL(12,0))                                     AS [Forecast demand],
       CAST(100.0 * SUM(ABS(f.forecast_demand - f.actual_demand)) / SUM(f.actual_demand) AS DECIMAL(5,1)) AS [WAPE %],
       CAST(100.0 * (SUM(f.forecast_demand) - SUM(f.actual_demand)) / SUM(f.actual_demand) AS DECIMAL(5,1)) AS [Bias %]
FROM dw.Fact_Demand_Forecast f
JOIN dw.Dim_Service s ON s.service_key = f.service_key
GROUP BY s.service_key, s.service_name, f.model_name
ORDER BY s.service_key, [WAPE %];

/* ---- Result Set B ------------------------------------------------------- */
SELECT v.vehicle_name                                                                    AS [Vehicle],
       f.model_name                                                                      AS [Model],
       SUM(f.actual_partners)                                                            AS [Actual partner-hours],
       CAST(SUM(f.forecast_partners) AS DECIMAL(12,0))                                   AS [Forecast partner-hours],
       CAST(100.0 * SUM(ABS(f.forecast_partners - f.actual_partners)) / SUM(f.actual_partners) AS DECIMAL(5,1)) AS [WAPE %],
       CAST(100.0 * (SUM(f.forecast_partners) - SUM(f.actual_partners)) / SUM(f.actual_partners) AS DECIMAL(5,1)) AS [Bias %]
FROM dw.Fact_Supply_Forecast f
JOIN dw.Dim_Vehicle v ON v.vehicle_key = f.vehicle_key
GROUP BY v.vehicle_key, v.vehicle_name, f.model_name
ORDER BY v.vehicle_key, [WAPE %];
