/* =========================================================================
   PULSE Phase 7 - 04: Empty kilometres — driving that earns nothing
   Result Set A: by zone type — pickup distance and empty km per busy hour
   Result Set B: by weekday hour — pickup distance, ETA and empty km
   Empty km = km driven to reach a pickup (no passenger or order on board).
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH rides AS (
    SELECT z.zone_type, AVG(f.pickup_km) AS ride_pickup_km, AVG(f.trip_km) AS ride_trip_km
    FROM dw.Fact_Rides f JOIN dw.Dim_Zone z ON z.zone_key = f.pickup_zone_key
    GROUP BY z.zone_type
),
food AS (
    SELECT z.zone_type, AVG(o.pickup_km) AS food_pickup_km, AVG(o.delivery_km) AS food_trip_km
    FROM dw.Fact_Food_Orders o JOIN dw.Dim_Zone z ON z.zone_key = o.restaurant_zone_key
    WHERE o.is_delivered = 1
    GROUP BY z.zone_type
),
supply AS (
    SELECT z.zone_type, SUM(s.empty_km) AS empty_km, SUM(s.busy_hours) AS busy_hours
    FROM dw.vw_Supply_ZoneHour s JOIN dw.Dim_Zone z ON z.zone_key = s.zone_key
    GROUP BY z.zone_type
)
SELECT r.zone_type                                                            AS [Zone type],
       CAST(r.ride_pickup_km AS DECIMAL(5,2))                                 AS [Avg ride pickup km],
       CAST(r.ride_trip_km   AS DECIMAL(5,2))                                 AS [Avg ride trip km],
       CAST(f.food_pickup_km AS DECIMAL(5,2))                                 AS [Avg food pickup km],
       CAST(f.food_trip_km   AS DECIMAL(5,2))                                 AS [Avg food delivery km],
       CAST(s.empty_km / NULLIF(s.busy_hours, 0) AS DECIMAL(6,2))             AS [Empty km per busy hour]
FROM rides r
JOIN food f   ON f.zone_type = r.zone_type
JOIN supply s ON s.zone_type = r.zone_type
ORDER BY [Avg ride pickup km] DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH rides AS (
    SELECT t.hour_of_day, COUNT(*) AS rides, AVG(f.pickup_km) AS pickup_km, SUM(f.pickup_km) AS empty_km,
           AVG(r.pickup_eta_min) AS eta
    FROM dw.Fact_Rides f
    JOIN dw.Fact_Ride_Requests r ON r.ride_request_key = f.ride_request_key
    JOIN dw.Dim_Time t ON t.time_key = f.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY t.hour_of_day
),
food AS (
    SELECT t.hour_of_day, COUNT(*) AS orders, AVG(o.pickup_km) AS pickup_km, SUM(o.pickup_km) AS empty_km
    FROM dw.Fact_Food_Orders o
    JOIN dw.Dim_Time t ON t.time_key = o.time_key
    WHERE o.is_delivered = 1 AND t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY t.hour_of_day
)
SELECT r.hour_of_day                                                          AS [Hour],
       CAST((r.rides + f.orders) / @weekdays AS DECIMAL(8,0))                 AS [Completed jobs per day],
       CAST(r.pickup_km AS DECIMAL(5,2))                                      AS [Avg ride pickup km],
       CAST(r.eta       AS DECIMAL(5,1))                                      AS [Avg ride pickup ETA (min)],
       CAST(f.pickup_km AS DECIMAL(5,2))                                      AS [Avg food pickup km],
       CAST((r.empty_km + f.empty_km) / @weekdays AS DECIMAL(8,0))            AS [Empty km per day]
FROM rides r
JOIN food f ON f.hour_of_day = r.hour_of_day
ORDER BY r.hour_of_day;
