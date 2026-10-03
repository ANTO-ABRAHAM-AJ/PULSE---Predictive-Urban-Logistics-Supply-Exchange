/* =========================================================================
   PULSE Phase 8 - 03: What kind of shortage is it — and which lever fixes it?
   Result Set A: lost jobs by shortage type, with the matching lever
   Result Set B: per zone — lost jobs per day by shortage type
   All 112 days.
   ========================================================================= */
USE PULSE_DW;

DECLARE @days DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH s AS (
    SELECT shortage_type,
           COUNT(*) AS zone_hours,
           SUM(lost_rides + lost_orders) AS lost
    FROM dw.Agg_Pressure_ZoneHour
    GROUP BY shortage_type
)
SELECT shortage_type                                                      AS [Shortage type],
       zone_hours                                                         AS [Zone-hours],
       lost                                                               AS [Jobs lost],
       CAST(100.0 * lost / SUM(lost) OVER () AS DECIMAL(5,1))             AS [Share of lost jobs %],
       CASE shortage_type
            WHEN 'Fix now'           THEN 'Better same-hour dispatch'
            WHEN 'Reposition ahead'  THEN 'Move supply before demand (Phase 10)'
            WHEN 'Citywide shortage' THEN 'Bring more partners online (Phase 11)'
            ELSE 'No shortage in the zone-hour' END                       AS [Lever]
FROM s
ORDER BY CASE shortage_type WHEN 'Reposition ahead' THEN 1 WHEN 'Citywide shortage' THEN 2
                            WHEN 'Fix now' THEN 3 ELSE 4 END;

/* ---- Result Set B ------------------------------------------------------- */
SELECT z.zone_code                                                                          AS [Zone],
       z.zone_type                                                                          AS [Zone type],
       CAST(SUM(CASE WHEN p.shortage_type = 'Fix now'           THEN p.lost_rides + p.lost_orders ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Lost per day: fix now],
       CAST(SUM(CASE WHEN p.shortage_type = 'Reposition ahead'  THEN p.lost_rides + p.lost_orders ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Lost per day: reposition ahead],
       CAST(SUM(CASE WHEN p.shortage_type = 'Citywide shortage' THEN p.lost_rides + p.lost_orders ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Lost per day: citywide shortage],
       CAST(SUM(CASE WHEN p.shortage_type = 'None'              THEN p.lost_rides + p.lost_orders ELSE 0 END) / @days AS DECIMAL(8,1)) AS [Lost per day: no shortage],
       CAST(SUM(p.lost_rides + p.lost_orders) / @days AS DECIMAL(8,1))                       AS [Lost per day: total]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
GROUP BY z.zone_code, z.zone_type
ORDER BY [Lost per day: total] DESC;
