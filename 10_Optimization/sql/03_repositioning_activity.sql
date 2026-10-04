/* =========================================================================
   PULSE Phase 10 - 03: Repositioning activity
   Result Set A: the 15 busiest corridors under the profit policy
   Result Set B: moves by hour of day for both policies
   ========================================================================= */
USE PULSE_DW;

DECLARE @days DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split = 'holdout');

/* ---- Result Set A ------------------------------------------------------- */
SELECT TOP (15)
       o.zone_code + ' -> ' + d.zone_code                                    AS [Corridor],
       o.zone_type + ' -> ' + d.zone_type                                    AS [Zone types],
       CAST(COUNT(*) / @days AS DECIMAL(8,1))                                AS [Moves per day],
       CAST(AVG(r.reposition_km) AS DECIMAL(6,1))                            AS [Avg move km],
       CAST(AVG(r.reposition_minutes) AS DECIMAL(6,1))                       AS [Avg move (min)],
       CAST(SUM(r.reposition_cost) / @days AS DECIMAL(10,0))                 AS [Cost per day (INR)]
FROM dw.Fact_Repositioning r
JOIN dw.Dim_Zone o ON o.zone_key = r.origin_zone_key
JOIN dw.Dim_Zone d ON d.zone_key = r.dest_zone_key
WHERE r.scenario_code = 'optimizer_profit'
GROUP BY o.zone_code, d.zone_code, o.zone_type, d.zone_type
ORDER BY COUNT(*) DESC;

/* ---- Result Set B ------------------------------------------------------- */
SELECT t.hour_of_day                                                                          AS [Hour],
       CAST(SUM(CASE WHEN r.scenario_code = 'optimizer_profit'  THEN 1 ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Moves per day: profit],
       CAST(SUM(CASE WHEN r.scenario_code = 'optimizer_service' THEN 1 ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Moves per day: service],
       CAST(SUM(CASE WHEN r.scenario_code = 'optimizer_profit'  THEN r.reposition_cost ELSE 0 END) / @days AS DECIMAL(10,0)) AS [Cost per day: profit (INR)],
       CAST(SUM(CASE WHEN r.scenario_code = 'optimizer_service' THEN r.reposition_cost ELSE 0 END) / @days AS DECIMAL(10,0)) AS [Cost per day: service (INR)]
FROM dw.Fact_Repositioning r
JOIN dw.Dim_Time t ON t.time_key = r.time_key
WHERE r.scenario_code IN ('optimizer_profit', 'optimizer_service')
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;
