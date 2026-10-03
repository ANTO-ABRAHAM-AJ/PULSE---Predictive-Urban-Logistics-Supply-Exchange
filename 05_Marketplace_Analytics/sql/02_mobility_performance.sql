/* =========================================================================
   PULSE Phase 5 - 02: Mobility performance
   Result Set A: ride KPIs by pickup zone type
   Result Set B: weekday hour-of-day profile
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) =
    (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
SELECT z.zone_type                                                              AS [Zone type],
       SUM(m.ride_requests)                                                     AS [Ride requests],
       CAST(100.0 * SUM(m.completed_rides)      / SUM(m.ride_requests) AS DECIMAL(5,1)) AS [Completion %],
       CAST(100.0 * SUM(m.cancelled_no_partner) / SUM(m.ride_requests) AS DECIMAL(5,1)) AS [No partner %],
       CAST(100.0 * SUM(m.cancelled_customer)   / SUM(m.ride_requests) AS DECIMAL(5,1)) AS [Customer cancel %],
       CAST(SUM(m.pickup_eta_min_sum) / NULLIF(SUM(m.completed_rides), 0) AS DECIMAL(5,1)) AS [Avg pickup ETA (min)],
       CAST(SUM(m.trip_km_sum)        / NULLIF(SUM(m.completed_rides), 0) AS DECIMAL(5,1)) AS [Avg trip km],
       CAST(SUM(m.platform_revenue) AS DECIMAL(14,0))                           AS [Platform revenue (INR)]
FROM dw.vw_Mobility_ZoneHour m
JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
GROUP BY z.zone_type
ORDER BY [Completion %];

/* ---- Result Set B ------------------------------------------------------- */
SELECT t.hour_of_day                                                            AS [Hour],
       CAST(SUM(m.ride_requests) / @weekdays AS DECIMAL(8,0))                   AS [Requests per weekday],
       CAST(100.0 * SUM(m.completed_rides)      / SUM(m.ride_requests) AS DECIMAL(5,1)) AS [Completion %],
       CAST(SUM(m.cancelled_no_partner) / @weekdays AS DECIMAL(8,0))            AS [Lost to no partner per weekday],
       CAST(SUM(m.pickup_eta_min_sum) / NULLIF(SUM(m.completed_rides), 0) AS DECIMAL(5,1)) AS [Avg pickup ETA (min)]
FROM dw.vw_Mobility_ZoneHour m
JOIN dw.Dim_Time t ON t.time_key = m.time_key
WHERE t.is_weekend = 0
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;
