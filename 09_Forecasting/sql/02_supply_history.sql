/* PULSE Phase 9 - 02: baseline supply history for forecasting.
   Partners online per hour, by HOME zone and vehicle type (where supply
   starts before any dispatch or repositioning), zeros included. */
USE PULSE_DW;

WITH online AS (
    SELECT a.time_key, d.home_zone_key, d.vehicle_key, COUNT(*) AS partners
    FROM dw.Fact_Driver_Availability a
    JOIN dw.Dim_Driver d ON d.driver_key = a.driver_key
    GROUP BY a.time_key, d.home_zone_key, d.vehicle_key
)
SELECT t.time_key, t.date_value, t.hour_of_day, t.day_of_week, t.is_weekend,
       t.is_rain_day, t.data_split,
       z.zone_key, z.zone_code, v.vehicle_key, v.vehicle_code,
       ISNULL(o.partners, 0) AS partners
FROM dw.Dim_Time t
CROSS JOIN dw.Dim_Zone z
CROSS JOIN dw.Dim_Vehicle v
LEFT JOIN online o ON o.time_key = t.time_key AND o.home_zone_key = z.zone_key AND o.vehicle_key = v.vehicle_key
WHERE t.data_split <> 'spill'
ORDER BY z.zone_key, v.vehicle_key, t.time_key;
