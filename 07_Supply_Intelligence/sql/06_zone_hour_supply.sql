/* =========================================================================
   PULSE Phase 7 - 06: Data for the Supply Map and heatmaps
   Result 1: zone x weekday hour — partners online, busy and idle per weekday
   Result 2: partners living in each zone
   Used by scripts/report_phase7.py; not a findings document on its own.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

SELECT z.zone_code                                                AS zone_code,
       z.zone_type                                                AS zone_type,
       t.hour_of_day                                              AS hour_of_day,
       CAST(SUM(s.online_hours) / @weekdays AS DECIMAL(10,2))     AS partners_online,
       CAST(SUM(s.busy_hours)   / @weekdays AS DECIMAL(10,2))     AS busy_hours,
       CAST(SUM(s.idle_hours)   / @weekdays AS DECIMAL(10,2))     AS idle_hours,
       CAST(100.0 * SUM(s.busy_hours) / NULLIF(SUM(s.online_hours), 0) AS DECIMAL(6,2)) AS utilization_pct
FROM dw.vw_Supply_ZoneHour s
JOIN dw.Dim_Time t ON t.time_key = s.time_key
JOIN dw.Dim_Zone z ON z.zone_key = s.zone_key
WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
GROUP BY z.zone_code, z.zone_type, t.hour_of_day
ORDER BY z.zone_code, t.hour_of_day;

SELECT z.zone_code AS zone_code, COUNT(d.driver_key) AS partners_living
FROM dw.Dim_Zone z
LEFT JOIN dw.Dim_Driver d ON d.home_zone_key = z.zone_key
GROUP BY z.zone_code
ORDER BY z.zone_code;
