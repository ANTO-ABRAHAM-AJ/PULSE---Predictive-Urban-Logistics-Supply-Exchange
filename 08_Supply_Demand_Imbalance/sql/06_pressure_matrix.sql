/* =========================================================================
   PULSE Phase 8 - 06: Data for the Pressure Map and heatmaps
   One row per zone and weekday hour. Used by scripts/report_phase8.py.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

SELECT z.zone_code AS zone_code,
       z.zone_type AS zone_type,
       t.hour_of_day AS hour_of_day,
       CAST(SUM(p.work_hours) / NULLIF(SUM(p.supply_hours), 0) AS DECIMAL(8,3)) AS mpi,
       CAST(100.0 * SUM(CASE WHEN p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END) / @weekdays AS DECIMAL(6,2)) AS under_pct,
       CAST(SUM(p.lost_rides + p.lost_orders) / @weekdays AS DECIMAL(10,2)) AS lost_per_day,
       CAST(SUM(CASE WHEN p.shortage_type = 'Fix now'           THEN p.lost_rides + p.lost_orders ELSE 0 END) / @weekdays AS DECIMAL(10,2)) AS lost_fix_now,
       CAST(SUM(CASE WHEN p.shortage_type = 'Reposition ahead'  THEN p.lost_rides + p.lost_orders ELSE 0 END) / @weekdays AS DECIMAL(10,2)) AS lost_reposition_ahead,
       CAST(SUM(CASE WHEN p.shortage_type = 'Citywide shortage' THEN p.lost_rides + p.lost_orders ELSE 0 END) / @weekdays AS DECIMAL(10,2)) AS lost_citywide
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
WHERE t.is_weekend = 0
GROUP BY z.zone_code, z.zone_type, t.hour_of_day
ORDER BY z.zone_code, t.hour_of_day;
