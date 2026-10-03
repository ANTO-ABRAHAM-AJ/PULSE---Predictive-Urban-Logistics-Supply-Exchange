/* PULSE Phase 9 - 01: demand history for forecasting.
   One row per hour x zone x service for all 112 days, zeros included. */
USE PULSE_DW;

SELECT t.time_key, t.date_value, t.hour_of_day, t.day_of_week, t.is_weekend,
       t.is_rain_day, t.is_event_day, t.data_split,
       z.zone_key, z.zone_code, z.zone_type,
       s.service_key, s.service_code,
       ISNULL(m.demand, 0) AS demand
FROM dw.Dim_Time t
CROSS JOIN dw.Dim_Zone z
CROSS JOIN dw.Dim_Service s
LEFT JOIN dw.vw_Marketplace_ZoneHour m
       ON m.time_key = t.time_key AND m.zone_key = z.zone_key AND m.service_key = s.service_key
WHERE t.data_split <> 'spill'
ORDER BY z.zone_key, s.service_key, t.time_key;
