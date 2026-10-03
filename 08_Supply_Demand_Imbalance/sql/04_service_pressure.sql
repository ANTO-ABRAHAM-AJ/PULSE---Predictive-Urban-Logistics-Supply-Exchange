/* =========================================================================
   PULSE Phase 8 - 04: Pressure by service — rides vs food
   Result Set A: weekday hour — city-level mobility and food MPI, and losses
   Result Set B: by zone type — share of weekday hours each service is short
   Mobility MPI = rides / (2 x all partners present);
   Food MPI     = orders / (3 x two-wheelers present).
   Each treats the shared two-wheelers as fully available to that service,
   so the two indices show each service's pressure on its own.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
SELECT t.hour_of_day                                                                     AS [Hour],
       CAST(SUM(p.ride_requests) / NULLIF(2.0 * SUM(p.supply_hours), 0) AS DECIMAL(6,2))  AS [Mobility MPI],
       CAST(SUM(p.food_orders) / NULLIF(3.0 * SUM(p.two_wheeler_hours), 0) AS DECIMAL(6,2)) AS [Food MPI],
       CAST(SUM(p.lost_rides)  / @weekdays AS DECIMAL(8,1))                               AS [Rides lost per weekday],
       CAST(SUM(p.lost_orders) / @weekdays AS DECIMAL(8,1))                               AS [Orders lost per weekday]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
WHERE t.is_weekend = 0
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;

/* ---- Result Set B ------------------------------------------------------- */
SELECT z.zone_type                                                                       AS [Zone type],
       CAST(100.0 * SUM(CASE WHEN p.ride_requests > 0 AND (p.mobility_mpi IS NULL OR p.mobility_mpi > 1.10) THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN p.ride_requests > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1)) AS [Mobility short hours %],
       CAST(100.0 * SUM(CASE WHEN p.food_orders > 0 AND (p.food_mpi IS NULL OR p.food_mpi > 1.10) THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN p.food_orders > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1))   AS [Food short hours %],
       CAST(SUM(p.lost_rides)  / @weekdays AS DECIMAL(8,1))                              AS [Rides lost per weekday],
       CAST(SUM(p.lost_orders) / @weekdays AS DECIMAL(8,1))                              AS [Orders lost per weekday]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
WHERE t.is_weekend = 0
GROUP BY z.zone_type
ORDER BY [Mobility short hours %] DESC;
