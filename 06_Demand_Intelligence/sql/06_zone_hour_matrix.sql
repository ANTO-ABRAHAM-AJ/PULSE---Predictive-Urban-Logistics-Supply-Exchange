/* =========================================================================
   PULSE Phase 6 - 06: Zone x hour matrix (data for the maps and heatmaps)
   One row per zone and weekday hour: demand and lost jobs per weekday.
   Used by scripts/report_phase6.py; not a findings document on its own.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

SELECT z.zone_code                                                                   AS zone_code,
       z.zone_type                                                                   AS zone_type,
       t.hour_of_day                                                                 AS hour_of_day,
       CAST(SUM(CASE WHEN m.service_key = 1 THEN m.demand ELSE 0 END) / @weekdays AS DECIMAL(10,2)) AS rides_per_day,
       CAST(SUM(CASE WHEN m.service_key = 2 THEN m.demand ELSE 0 END) / @weekdays AS DECIMAL(10,2)) AS orders_per_day,
       CAST(SUM(m.lost_no_partner) / @weekdays AS DECIMAL(10,2))                     AS lost_per_day
FROM dw.vw_Marketplace_ZoneHour m
JOIN dw.Dim_Time t ON t.time_key = m.time_key
JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
GROUP BY z.zone_code, z.zone_type, t.hour_of_day
ORDER BY z.zone_code, t.hour_of_day;
