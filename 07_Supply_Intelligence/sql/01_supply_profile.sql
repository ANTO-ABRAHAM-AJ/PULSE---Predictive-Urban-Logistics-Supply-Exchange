/* =========================================================================
   PULSE Phase 7 - 01: Supply profile — where partners live vs where they are
   Result Set A: per zone — partners living there, present, utilization, idle
   Result Set B: by zone type — share of partners living there vs present
                 at 09:00, 13:00 and 19:00 on weekdays (the daily drift)
   "Present" = partner's location at the start of each online hour.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH home AS (
    SELECT d.home_zone_key AS zone_key,
           COUNT(*) AS living,
           SUM(CASE WHEN v.can_food = 1 THEN 1 ELSE 0 END) AS living_tw
    FROM dw.Dim_Driver d
    JOIN dw.Dim_Vehicle v ON v.vehicle_key = d.vehicle_key
    GROUP BY d.home_zone_key
),
present AS (
    SELECT s.zone_key,
           SUM(CASE WHEN t.hour_of_day BETWEEN 8 AND 21 THEN s.online_hours ELSE 0 END) AS online_day_hours,
           SUM(s.online_hours) AS online_hours,
           SUM(s.busy_hours)   AS busy_hours,
           SUM(s.idle_hours)   AS idle_hours
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Time t ON t.time_key = s.time_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY s.zone_key
)
SELECT z.zone_code                                                                 AS [Zone],
       z.zone_type                                                                 AS [Zone type],
       ISNULL(h.living, 0)                                                         AS [Partners living here],
       CAST(100.0 * h.living_tw / NULLIF(h.living, 0) AS DECIMAL(5,1))             AS [Two-wheelers among them %],
       CAST(p.online_day_hours / @weekdays / 14 AS DECIMAL(8,1))                   AS [Avg partners present 08-21 per weekday],
       CAST(p.online_day_hours / @weekdays / 14 / NULLIF(h.living, 0) AS DECIMAL(6,2)) AS [Present to living ratio],
       CAST(100.0 * p.busy_hours / NULLIF(p.online_hours, 0) AS DECIMAL(5,1))      AS [Utilization %],
       CAST(p.idle_hours / @weekdays AS DECIMAL(8,1))                              AS [Idle partner-hours per weekday]
FROM dw.Dim_Zone z
LEFT JOIN home h    ON h.zone_key = z.zone_key
LEFT JOIN present p ON p.zone_key = z.zone_key
ORDER BY [Partners living here] DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH home AS (
    SELECT z.zone_type, COUNT(*) AS living
    FROM dw.Dim_Driver d JOIN dw.Dim_Zone z ON z.zone_key = d.home_zone_key
    GROUP BY z.zone_type
),
present AS (
    SELECT z.zone_type,
           SUM(CASE WHEN t.hour_of_day = 9  THEN s.partner_hours ELSE 0 END) AS at09,
           SUM(CASE WHEN t.hour_of_day = 13 THEN s.partner_hours ELSE 0 END) AS at13,
           SUM(CASE WHEN t.hour_of_day = 19 THEN s.partner_hours ELSE 0 END) AS at19
    FROM dw.vw_Supply_ZoneHour s
    JOIN dw.Dim_Time t ON t.time_key = s.time_key
    JOIN dw.Dim_Zone z ON z.zone_key = s.zone_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY z.zone_type
)
SELECT h.zone_type                                                              AS [Zone type],
       CAST(100.0 * h.living / SUM(h.living) OVER () AS DECIMAL(5,1))           AS [Partners living here %],
       CAST(100.0 * p.at09 / SUM(p.at09) OVER () AS DECIMAL(5,1))               AS [Present at 09:00 %],
       CAST(100.0 * p.at13 / SUM(p.at13) OVER () AS DECIMAL(5,1))               AS [Present at 13:00 %],
       CAST(100.0 * p.at19 / SUM(p.at19) OVER () AS DECIMAL(5,1))               AS [Present at 19:00 %]
FROM home h
JOIN present p ON p.zone_type = h.zone_type
ORDER BY [Partners living here %] DESC;
