/* =========================================================================
   PULSE Phase 6 - 01: Zone demand profile
   Result Set A: every zone's weekday demand, share, weekend effect, peak hours
   Result Set B: the 10 busiest weekday zone-hours
   Built on the Phase 5 KPI views (dw.vw_Marketplace_ZoneHour).
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');
DECLARE @weekends DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 1 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH zone_day AS (
    SELECT m.zone_key,
           SUM(CASE WHEN t.is_weekend = 0 AND m.service_key = 1 THEN m.demand ELSE 0 END) / @weekdays AS rides_wd,
           SUM(CASE WHEN t.is_weekend = 0 AND m.service_key = 2 THEN m.demand ELSE 0 END) / @weekdays AS orders_wd,
           SUM(CASE WHEN t.is_weekend = 0 THEN m.demand ELSE 0 END) / @weekdays                      AS jobs_wd,
           SUM(CASE WHEN t.is_weekend = 1 THEN m.demand ELSE 0 END) / @weekends                      AS jobs_we
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.data_split <> 'spill'
    GROUP BY m.zone_key
),
hourly AS (
    SELECT m.zone_key, m.service_key, t.hour_of_day,
           ROW_NUMBER() OVER (PARTITION BY m.zone_key, m.service_key
                              ORDER BY SUM(m.demand) DESC, t.hour_of_day) AS rn
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY m.zone_key, m.service_key, t.hour_of_day
)
SELECT z.zone_code                                                           AS [Zone],
       z.zone_name                                                           AS [Zone name],
       z.zone_type                                                           AS [Zone type],
       CAST(d.rides_wd  AS DECIMAL(8,0))                                     AS [Rides per weekday],
       CAST(d.orders_wd AS DECIMAL(8,0))                                     AS [Orders per weekday],
       CAST(100.0 * d.jobs_wd / SUM(d.jobs_wd) OVER () AS DECIMAL(5,1))      AS [Share of weekday demand %],
       CAST(d.jobs_we / NULLIF(d.jobs_wd, 0) AS DECIMAL(5,2))                AS [Weekend to weekday ratio],
       pr.hour_of_day                                                        AS [Peak ride hour],
       pf.hour_of_day                                                        AS [Peak food hour]
FROM zone_day d
JOIN dw.Dim_Zone z ON z.zone_key = d.zone_key
JOIN hourly pr ON pr.zone_key = d.zone_key AND pr.service_key = 1 AND pr.rn = 1
JOIN hourly pf ON pf.zone_key = d.zone_key AND pf.service_key = 2 AND pf.rn = 1
ORDER BY [Share of weekday demand %] DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH zh AS (
    SELECT m.zone_key, t.hour_of_day,
           SUM(CASE WHEN m.service_key = 1 THEN m.demand ELSE 0 END) / @weekdays AS rides,
           SUM(CASE WHEN m.service_key = 2 THEN m.demand ELSE 0 END) / @weekdays AS orders,
           SUM(m.demand) / @weekdays                                             AS jobs
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY m.zone_key, t.hour_of_day
)
SELECT TOP (10)
       z.zone_code                                                           AS [Zone],
       z.zone_type                                                           AS [Zone type],
       zh.hour_of_day                                                        AS [Hour],
       CAST(zh.rides  AS DECIMAL(8,0))                                       AS [Rides per day],
       CAST(zh.orders AS DECIMAL(8,0))                                       AS [Orders per day],
       CAST(zh.jobs   AS DECIMAL(8,0))                                       AS [Jobs per day],
       CAST(100.0 * zh.jobs / SUM(zh.jobs) OVER () AS DECIMAL(5,2))          AS [Share of weekday demand %]
FROM zh
JOIN dw.Dim_Zone z ON z.zone_key = zh.zone_key
ORDER BY zh.jobs DESC;
