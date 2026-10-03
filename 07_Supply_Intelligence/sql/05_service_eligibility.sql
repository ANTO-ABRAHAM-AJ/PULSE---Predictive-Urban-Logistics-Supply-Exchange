/* =========================================================================
   PULSE Phase 7 - 05: Service eligibility — two-wheelers vs four-wheelers
   Result Set A: by zone type — where each vehicle type is, and how busy
   Result Set B: by weekday hour — vehicles online, utilization, and how
                 two-wheeler busy time splits between rides and food
   Two-wheelers can serve rides and food; four-wheelers serve rides only.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH s AS (
    SELECT z.zone_type, v.can_food,
           SUM(x.online_hours) AS online, SUM(x.busy_hours) AS busy
    FROM dw.vw_Supply_ZoneHour x
    JOIN dw.Dim_Zone z    ON z.zone_key = x.zone_key
    JOIN dw.Dim_Vehicle v ON v.vehicle_key = x.vehicle_key
    JOIN dw.Dim_Time t    ON t.time_key = x.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY z.zone_type, v.can_food
),
served AS (
    SELECT z.zone_type,
           SUM(CASE WHEN f.vehicle_key = 2 THEN 1 ELSE 0 END) AS by_cab,
           COUNT(*) AS rides
    FROM dw.Fact_Rides f JOIN dw.Dim_Zone z ON z.zone_key = f.pickup_zone_key
    GROUP BY z.zone_type
)
SELECT tw.zone_type                                                                 AS [Zone type],
       CAST(100.0 * tw.online / (tw.online + fw.online) AS DECIMAL(5,1))            AS [Two-wheeler share of online time %],
       CAST(100.0 * tw.busy / NULLIF(tw.online, 0) AS DECIMAL(5,1))                 AS [Two-wheeler utilization %],
       CAST(100.0 * fw.busy / NULLIF(fw.online, 0) AS DECIMAL(5,1))                 AS [Four-wheeler utilization %],
       CAST(100.0 * sv.by_cab / NULLIF(sv.rides, 0) AS DECIMAL(5,1))                AS [Rides served by cab %]
FROM s tw
JOIN s fw       ON fw.zone_type = tw.zone_type AND fw.can_food = 0
JOIN served sv  ON sv.zone_type = tw.zone_type
WHERE tw.can_food = 1
ORDER BY [Two-wheeler share of online time %] DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH s AS (
    SELECT t.hour_of_day,
           SUM(CASE WHEN v.can_food = 1 THEN x.online_hours ELSE 0 END) AS tw_online,
           SUM(CASE WHEN v.can_food = 0 THEN x.online_hours ELSE 0 END) AS fw_online,
           SUM(CASE WHEN v.can_food = 1 THEN x.busy_hours ELSE 0 END)   AS tw_busy,
           SUM(CASE WHEN v.can_food = 0 THEN x.busy_hours ELSE 0 END)   AS fw_busy
    FROM dw.vw_Supply_ZoneHour x
    JOIN dw.Dim_Vehicle v ON v.vehicle_key = x.vehicle_key
    JOIN dw.Dim_Time t    ON t.time_key = x.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY t.hour_of_day
),
tw_jobs AS (                       -- two-wheeler job minutes by service, by start hour
    SELECT t.hour_of_day,
           SUM(CASE WHEN j.service = 'ride' THEN j.minutes ELSE 0 END) AS ride_min,
           SUM(j.minutes) AS all_min
    FROM (
        SELECT f.time_key, 'ride' AS service, DATEDIFF(SECOND, r.assigned_ts, f.dropoff_ts) / 60.0 AS minutes
        FROM dw.Fact_Rides f JOIN dw.Fact_Ride_Requests r ON r.ride_request_key = f.ride_request_key
        WHERE f.vehicle_key = 1
        UNION ALL
        SELECT o.time_key, 'food', DATEDIFF(SECOND, o.assigned_ts, o.delivered_ts) / 60.0
        FROM dw.Fact_Food_Orders o WHERE o.is_delivered = 1
    ) j
    JOIN dw.Dim_Time t ON t.time_key = j.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY t.hour_of_day
)
SELECT s.hour_of_day                                                               AS [Hour],
       CAST(s.tw_online / @weekdays AS DECIMAL(8,0))                               AS [Two-wheelers online],
       CAST(s.fw_online / @weekdays AS DECIMAL(8,0))                               AS [Four-wheelers online],
       CAST(100.0 * s.tw_busy / NULLIF(s.tw_online, 0) AS DECIMAL(5,1))            AS [Two-wheeler utilization %],
       CAST(100.0 * s.fw_busy / NULLIF(s.fw_online, 0) AS DECIMAL(5,1))            AS [Four-wheeler utilization %],
       CAST(100.0 * j.ride_min / NULLIF(j.all_min, 0) AS DECIMAL(5,1))             AS [Two-wheeler busy time on rides %]
FROM s
LEFT JOIN tw_jobs j ON j.hour_of_day = s.hour_of_day
ORDER BY s.hour_of_day;
