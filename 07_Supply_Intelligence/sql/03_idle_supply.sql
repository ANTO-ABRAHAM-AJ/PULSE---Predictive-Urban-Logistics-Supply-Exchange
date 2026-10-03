/* =========================================================================
   PULSE Phase 7 - 03: Idle supply and its distance to unserved demand
   Result Set A: the 15 weekday zone-hours with the most idle partner-hours
   Result Set B: per weekday hour — how much idle supply was within reach of
                 a zone that was losing jobs in that same hour
   Reach = 20 minutes of travel (Assumption C-06): 5 km at weekday peak
   (15 km/h), 8.3 km otherwise (25 km/h). Road km = straight-line km x 1.4
   (Assumption C-04), computed from zone centroids with the geography type.
   A zone is "losing jobs" in an hour if it loses at least 1 job per weekday.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH idle AS (
    SELECT s.zone_key, t.hour_of_day,
           SUM(s.online_hours) / @weekdays AS online,
           SUM(s.idle_hours)   / @weekdays AS idle,
           SUM(s.busy_hours)   AS busy, SUM(s.online_hours) AS online_total
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Time t ON t.time_key = s.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY s.zone_key, t.hour_of_day
),
lost AS (
    SELECT m.zone_key, t.hour_of_day, SUM(m.lost_no_partner) / @weekdays AS lost
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY m.zone_key, t.hour_of_day
)
SELECT TOP (15)
       z.zone_code                                                          AS [Zone],
       z.zone_type                                                          AS [Zone type],
       i.hour_of_day                                                        AS [Hour],
       CAST(i.online AS DECIMAL(8,1))                                       AS [Partners online],
       CAST(i.idle   AS DECIMAL(8,1))                                       AS [Idle partner-hours],
       CAST(100.0 * i.busy / NULLIF(i.online_total, 0) AS DECIMAL(5,1))     AS [Utilization %],
       CAST(ISNULL(l.lost, 0) AS DECIMAL(8,1))                              AS [Jobs lost in this zone-hour]
FROM idle i
JOIN dw.Dim_Zone z ON z.zone_key = i.zone_key
LEFT JOIN lost l   ON l.zone_key = i.zone_key AND l.hour_of_day = i.hour_of_day
ORDER BY i.idle DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH idle AS (
    SELECT s.zone_key, t.hour_of_day, SUM(s.idle_hours) / @weekdays AS idle
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Time t ON t.time_key = s.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY s.zone_key, t.hour_of_day
),
lost AS (
    SELECT m.zone_key, t.hour_of_day, SUM(m.lost_no_partner) / @weekdays AS lost
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY m.zone_key, t.hour_of_day
),
road_km AS (                      -- zone-to-zone road distance (0 within a zone)
    SELECT a.zone_key AS from_zone, b.zone_key AS to_zone,
           CASE WHEN a.zone_key = b.zone_key THEN 0.0
                ELSE geography::Point(a.latitude, a.longitude, 4326)
                       .STDistance(geography::Point(b.latitude, b.longitude, 4326)) / 1000.0 * 1.4
           END AS km
    FROM dw.Dim_Zone a CROSS JOIN dw.Dim_Zone b
),
reach AS (                        -- 20 minutes of travel at the hour's weekday speed
    SELECT hour_of_day, CASE WHEN MAX(CAST(is_peak_hour AS INT)) = 1 THEN 5.0 ELSE 25.0 / 3 END AS km
    FROM dw.Dim_Time WHERE is_weekend = 0 GROUP BY hour_of_day
),
idle_near AS (
    SELECT i.hour_of_day, i.zone_key, i.idle,
           CASE WHEN EXISTS (SELECT 1 FROM lost l
                             JOIN road_km d ON d.from_zone = i.zone_key AND d.to_zone = l.zone_key
                             JOIN reach r   ON r.hour_of_day = i.hour_of_day
                             WHERE l.hour_of_day = i.hour_of_day AND l.lost >= 1 AND d.km <= r.km)
                THEN 1 ELSE 0 END AS near_loss
    FROM idle i
)
SELECT n.hour_of_day                                                           AS [Hour],
       CAST(SUM(n.idle) AS DECIMAL(8,0))                                       AS [Idle partner-hours],
       CAST((SELECT SUM(l.lost) FROM lost l WHERE l.hour_of_day = n.hour_of_day) AS DECIMAL(8,0)) AS [Jobs lost],
       (SELECT COUNT(*) FROM lost l WHERE l.hour_of_day = n.hour_of_day AND l.lost >= 1) AS [Zones losing jobs],
       CAST(SUM(n.idle * n.near_loss) AS DECIMAL(8,0))                         AS [Idle within reach of a losing zone],
       CAST(100.0 * SUM(n.idle * n.near_loss) / NULLIF(SUM(n.idle), 0) AS DECIMAL(5,1)) AS [Idle within reach %]
FROM idle_near n
GROUP BY n.hour_of_day
ORDER BY n.hour_of_day;
