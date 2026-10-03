/* =========================================================================
   PULSE Phase 6 - 03: Demand pressure (where demand goes unserved)
   Result Set A: the 15 weekday zone-hour-services losing the most jobs
   Result Set B: lost jobs per zone, by service
   "Lost" = cancelled because no partner could reach in time.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');
DECLARE @days     DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
SELECT TOP (15)
       z.zone_code                                                          AS [Zone],
       z.zone_type                                                          AS [Zone type],
       t.hour_of_day                                                        AS [Hour],
       s.service_name                                                       AS [Service],
       CAST(SUM(m.demand) / @weekdays AS DECIMAL(8,1))                      AS [Demand per day],
       CAST(SUM(m.lost_no_partner) / @weekdays AS DECIMAL(8,1))             AS [Lost per day],
       CAST(100.0 * SUM(m.lost_no_partner) / SUM(m.demand) AS DECIMAL(5,1)) AS [Lost %]
FROM dw.vw_Marketplace_ZoneHour m
JOIN dw.Dim_Time t    ON t.time_key = m.time_key
JOIN dw.Dim_Zone z    ON z.zone_key = m.zone_key
JOIN dw.Dim_Service s ON s.service_key = m.service_key
WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
GROUP BY z.zone_code, z.zone_type, t.hour_of_day, s.service_name
ORDER BY SUM(m.lost_no_partner) DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH zl AS (
    SELECT m.zone_key,
           SUM(CASE WHEN m.service_key = 1 THEN m.lost_no_partner ELSE 0 END) AS lost_rides,
           SUM(CASE WHEN m.service_key = 2 THEN m.lost_no_partner ELSE 0 END) AS lost_orders,
           SUM(CASE WHEN m.service_key = 1 THEN m.demand ELSE 0 END)          AS rides,
           SUM(CASE WHEN m.service_key = 2 THEN m.demand ELSE 0 END)          AS orders
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.data_split <> 'spill'
    GROUP BY m.zone_key
)
SELECT z.zone_code                                                                    AS [Zone],
       z.zone_type                                                                    AS [Zone type],
       CAST(zl.lost_rides  / @days AS DECIMAL(8,1))                                   AS [Lost rides per day],
       CAST(zl.lost_orders / @days AS DECIMAL(8,1))                                   AS [Lost orders per day],
       CAST(100.0 * zl.lost_rides  / NULLIF(zl.rides, 0)  AS DECIMAL(5,1))            AS [Ride loss %],
       CAST(100.0 * zl.lost_orders / NULLIF(zl.orders, 0) AS DECIMAL(5,1))            AS [Food loss %],
       CAST(100.0 * (zl.lost_rides + zl.lost_orders)
            / SUM(zl.lost_rides + zl.lost_orders) OVER () AS DECIMAL(5,1))            AS [Share of city losses %]
FROM zl
JOIN dw.Dim_Zone z ON z.zone_key = zl.zone_key
ORDER BY [Share of city losses %] DESC;
