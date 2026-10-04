/* =========================================================================
   PULSE Phase 10 - 02: Where and when the optimizer recovers lost demand
   Result Set A: lost jobs per day by zone — status quo vs the two policies
   Result Set B: lost jobs per weekday by hour
   ========================================================================= */
USE PULSE_DW;

DECLARE @days     DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split = 'holdout');
DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split = 'holdout' AND is_weekend = 0);

/* ---- Result Set A ------------------------------------------------------- */
WITH z AS (
    SELECT p.zone_key,
           SUM(CASE WHEN p.scenario_code = 'status_quo'        THEN p.lost_no_partner ELSE 0 END) AS sq,
           SUM(CASE WHEN p.scenario_code = 'optimizer_profit'  THEN p.lost_no_partner ELSE 0 END) AS prof,
           SUM(CASE WHEN p.scenario_code = 'optimizer_service' THEN p.lost_no_partner ELSE 0 END) AS serv
    FROM dw.Agg_Policy_ZoneHour p
    GROUP BY p.zone_key
)
SELECT dz.zone_code                                                         AS [Zone],
       dz.zone_type                                                         AS [Zone type],
       CAST(z.sq   / @days AS DECIMAL(8,1))                                 AS [Lost per day: status quo],
       CAST(z.prof / @days AS DECIMAL(8,1))                                 AS [Lost per day: profit policy],
       CAST(z.serv / @days AS DECIMAL(8,1))                                 AS [Lost per day: service policy],
       CAST(100.0 * (z.sq - z.prof) / NULLIF(z.sq, 0) AS DECIMAL(6,1))      AS [Recovered by profit policy %],
       CAST(100.0 * (z.sq - z.serv) / NULLIF(z.sq, 0) AS DECIMAL(6,1))      AS [Recovered by service policy %]
FROM z
JOIN dw.Dim_Zone dz ON dz.zone_key = z.zone_key
ORDER BY [Lost per day: status quo] DESC;

/* ---- Result Set B ------------------------------------------------------- */
SELECT t.hour_of_day                                                                       AS [Hour],
       CAST(SUM(CASE WHEN p.scenario_code = 'status_quo'        THEN p.lost_no_partner ELSE 0 END) / @weekdays AS DECIMAL(8,1)) AS [Lost: status quo],
       CAST(SUM(CASE WHEN p.scenario_code = 'optimizer_profit'  THEN p.lost_no_partner ELSE 0 END) / @weekdays AS DECIMAL(8,1)) AS [Lost: profit policy],
       CAST(SUM(CASE WHEN p.scenario_code = 'optimizer_service' THEN p.lost_no_partner ELSE 0 END) / @weekdays AS DECIMAL(8,1)) AS [Lost: service policy]
FROM dw.Agg_Policy_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
WHERE t.is_weekend = 0
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;
