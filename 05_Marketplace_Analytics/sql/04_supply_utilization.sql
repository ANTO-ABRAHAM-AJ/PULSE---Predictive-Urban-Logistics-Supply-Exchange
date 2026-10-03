/* =========================================================================
   PULSE Phase 5 - 04: Supply and utilization
   Result Set A: weekday hour profile - idle partners next to lost requests
   Result Set B: where partners are vs where work is, by zone type
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) =
    (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH supply AS (
    SELECT t.hour_of_day,
           SUM(s.online_hours) AS online_hours,
           SUM(s.busy_hours)   AS busy_hours,
           SUM(s.idle_hours)   AS idle_hours
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Time t ON t.time_key = s.time_key
    WHERE t.is_weekend = 0
    GROUP BY t.hour_of_day
),
lost AS (
    SELECT t.hour_of_day, SUM(m.lost_no_partner) AS lost_jobs
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.is_weekend = 0
    GROUP BY t.hour_of_day
)
SELECT s.hour_of_day                                                  AS [Hour],
       CAST(s.online_hours / @weekdays AS DECIMAL(8,0))               AS [Partners online],
       CAST(100.0 * s.busy_hours / s.online_hours AS DECIMAL(5,1))    AS [Utilization %],
       CAST(s.idle_hours / @weekdays AS DECIMAL(8,0))                 AS [Idle partner-hours],
       CAST(ISNULL(l.lost_jobs, 0) / @weekdays AS DECIMAL(8,0))       AS [Jobs lost to no partner]
FROM supply s
LEFT JOIN lost l ON l.hour_of_day = s.hour_of_day
ORDER BY s.hour_of_day;

/* ---- Result Set B ------------------------------------------------------- */
WITH work AS (                 -- partner-hours of work requested (Assumption O-01)
    SELECT z.zone_type,
           SUM(CASE WHEN m.service_key = 1 THEN m.demand / 2.0 ELSE m.demand / 3.0 END) AS work_hours
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
    GROUP BY z.zone_type
),
supply AS (
    SELECT z.zone_type,
           SUM(s.online_hours) AS online_hours,
           SUM(s.busy_hours)   AS busy_hours
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Zone z ON z.zone_key = s.zone_key
    GROUP BY z.zone_type
)
SELECT w.zone_type                                                                     AS [Zone type],
       CAST(100.0 * w.work_hours   / SUM(w.work_hours)   OVER () AS DECIMAL(5,1))      AS [Share of work %],
       CAST(100.0 * s.online_hours / SUM(s.online_hours) OVER () AS DECIMAL(5,1))      AS [Share of online partners %],
       CAST((w.work_hours / SUM(w.work_hours) OVER ())
            / (s.online_hours / SUM(s.online_hours) OVER ()) AS DECIMAL(5,2))          AS [Work-to-supply ratio],
       CAST(100.0 * s.busy_hours / s.online_hours AS DECIMAL(5,1))                     AS [Utilization %]
FROM work w
JOIN supply s ON s.zone_type = w.zone_type
ORDER BY [Work-to-supply ratio] DESC;
