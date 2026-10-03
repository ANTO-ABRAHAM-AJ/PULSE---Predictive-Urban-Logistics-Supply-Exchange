/* =========================================================================
   PULSE Phase 7 - 02: How partners spend their online time
   Result Set A: weekday hour — share of online time in each state
   Result Set B: by vehicle type — share of online time in each state
   States: idle | to pickup | on trip | to restaurant | delivering.
   Job segments are split exactly across the clock hours they span; busy time
   per hour (Fact_Driver_Availability) is then shared out by the segment mix,
   so the five states always add up to 100% of online time.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

IF OBJECT_ID('tempdb..#state_mix') IS NOT NULL DROP TABLE #state_mix;

WITH seg AS (                      -- every busy segment of every served job
    SELECT f.driver_key, r.assigned_ts AS s, f.pickup_ts  AS e, 'to_pickup' AS state
    FROM dw.Fact_Rides f JOIN dw.Fact_Ride_Requests r ON r.ride_request_key = f.ride_request_key
    UNION ALL
    SELECT f.driver_key, f.pickup_ts, f.dropoff_ts, 'on_trip'
    FROM dw.Fact_Rides f
    UNION ALL
    SELECT o.driver_key, o.assigned_ts, o.picked_ts, 'to_restaurant'
    FROM dw.Fact_Food_Orders o WHERE o.is_delivered = 1
    UNION ALL
    SELECT o.driver_key, o.picked_ts, o.delivered_ts, 'delivering'
    FROM dw.Fact_Food_Orders o WHERE o.is_delivered = 1
),
pieces AS (                        -- split each segment across clock hours
    SELECT seg.driver_key, seg.state, b.bucket,
           DATEDIFF(SECOND, GREATEST(seg.s, b.bucket), LEAST(seg.e, DATEADD(HOUR, 1, b.bucket))) / 60.0 AS minutes
    FROM seg
    CROSS APPLY (VALUES (0), (1), (2)) k(n)
    CROSS APPLY (SELECT DATEADD(HOUR, DATEDIFF(HOUR, CAST('2000-01-01' AS DATETIME2(0)), seg.s) + k.n,
                                CAST('2000-01-01' AS DATETIME2(0))) AS bucket) b
    WHERE seg.e > b.bucket AND seg.s < DATEADD(HOUR, 1, b.bucket)
)
SELECT YEAR(p.bucket) * 1000000 + MONTH(p.bucket) * 10000 + DAY(p.bucket) * 100 + DATEPART(HOUR, p.bucket) AS time_key,
       d.vehicle_key,
       SUM(CASE WHEN p.state = 'to_pickup'     THEN p.minutes ELSE 0 END) AS to_pickup,
       SUM(CASE WHEN p.state = 'on_trip'       THEN p.minutes ELSE 0 END) AS on_trip,
       SUM(CASE WHEN p.state = 'to_restaurant' THEN p.minutes ELSE 0 END) AS to_restaurant,
       SUM(CASE WHEN p.state = 'delivering'    THEN p.minutes ELSE 0 END) AS delivering,
       SUM(p.minutes)                                                     AS all_minutes
INTO #state_mix
FROM pieces p
JOIN dw.Dim_Driver d ON d.driver_key = p.driver_key
GROUP BY YEAR(p.bucket) * 1000000 + MONTH(p.bucket) * 10000 + DAY(p.bucket) * 100 + DATEPART(HOUR, p.bucket),
         d.vehicle_key;

IF OBJECT_ID('tempdb..#states') IS NOT NULL DROP TABLE #states;

SELECT t.hour_of_day, s.vehicle_key,
       SUM(s.online_hours) * 60                                                                     AS online_min,
       SUM(s.idle_hours) * 60                                                                       AS idle_min,
       SUM(s.busy_hours * 60 * ISNULL(m.to_pickup     / NULLIF(m.all_minutes, 0), 0))               AS to_pickup,
       SUM(s.busy_hours * 60 * ISNULL(m.on_trip       / NULLIF(m.all_minutes, 0), 0))               AS on_trip,
       SUM(s.busy_hours * 60 * ISNULL(m.to_restaurant / NULLIF(m.all_minutes, 0), 0))               AS to_restaurant,
       SUM(s.busy_hours * 60 * ISNULL(m.delivering    / NULLIF(m.all_minutes, 0), 0))               AS delivering
INTO #states
FROM (SELECT time_key, vehicle_key, SUM(online_hours) AS online_hours, SUM(busy_hours) AS busy_hours,
             SUM(idle_hours) AS idle_hours
      FROM dw.vw_Supply_ZoneHour GROUP BY time_key, vehicle_key) s
JOIN dw.Dim_Time t ON t.time_key = s.time_key
LEFT JOIN #state_mix m ON m.time_key = s.time_key AND m.vehicle_key = s.vehicle_key
WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
GROUP BY t.hour_of_day, s.vehicle_key;

/* ---- Result Set A ------------------------------------------------------- */
SELECT hour_of_day                                                          AS [Hour],
       CAST(SUM(online_min) / 60 / @weekdays AS DECIMAL(8,0))               AS [Partners online],
       CAST(100.0 * SUM(idle_min)      / SUM(online_min) AS DECIMAL(5,1))   AS [Idle %],
       CAST(100.0 * SUM(to_pickup)     / SUM(online_min) AS DECIMAL(5,1))   AS [To pickup %],
       CAST(100.0 * SUM(on_trip)       / SUM(online_min) AS DECIMAL(5,1))   AS [On trip %],
       CAST(100.0 * SUM(to_restaurant) / SUM(online_min) AS DECIMAL(5,1))   AS [To restaurant %],
       CAST(100.0 * SUM(delivering)    / SUM(online_min) AS DECIMAL(5,1))   AS [Delivering %]
FROM #states
GROUP BY hour_of_day
ORDER BY hour_of_day;

/* ---- Result Set B ------------------------------------------------------- */
SELECT v.vehicle_name                                                       AS [Vehicle],
       CAST(SUM(s.online_min) / 60 / @weekdays AS DECIMAL(10,0))            AS [Online partner-hours per weekday],
       CAST(100.0 * SUM(s.idle_min)      / SUM(s.online_min) AS DECIMAL(5,1)) AS [Idle %],
       CAST(100.0 * SUM(s.to_pickup)     / SUM(s.online_min) AS DECIMAL(5,1)) AS [To pickup %],
       CAST(100.0 * SUM(s.on_trip)       / SUM(s.online_min) AS DECIMAL(5,1)) AS [On trip %],
       CAST(100.0 * SUM(s.to_restaurant) / SUM(s.online_min) AS DECIMAL(5,1)) AS [To restaurant %],
       CAST(100.0 * SUM(s.delivering)    / SUM(s.online_min) AS DECIMAL(5,1)) AS [Delivering %]
FROM #states s
JOIN dw.Dim_Vehicle v ON v.vehicle_key = s.vehicle_key
GROUP BY v.vehicle_key, v.vehicle_name
ORDER BY v.vehicle_key;

DROP TABLE #states;
DROP TABLE #state_mix;
