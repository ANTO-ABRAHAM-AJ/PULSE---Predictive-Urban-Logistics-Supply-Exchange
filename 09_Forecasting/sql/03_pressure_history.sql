/* PULSE Phase 9 - 03: observed pressure history (from Phase 8) for the
   week-ahead pressure prediction. Needs dw.Agg_Pressure_ZoneHour. */
USE PULSE_DW;

SELECT p.time_key, t.date_value, t.hour_of_day, t.is_weekend, t.is_rain_day, t.data_split,
       p.zone_key, z.zone_code, z.zone_type,
       p.supply_hours, p.work_hours, p.pressure_state,
       p.lost_rides + p.lost_orders AS lost_jobs
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
ORDER BY p.zone_key, p.time_key;
