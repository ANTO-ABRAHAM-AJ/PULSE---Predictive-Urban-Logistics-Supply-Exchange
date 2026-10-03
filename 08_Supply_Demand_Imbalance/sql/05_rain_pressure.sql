/* =========================================================================
   PULSE Phase 8 - 05: Rain and pressure
   Result Set A: weekday time bands — city MPI and lost jobs, dry vs rain days
   Result Set B: by zone type — share of weekday hours under-supplied, dry vs rain
   Rain raises food demand and cuts two-wheeler supply (Assumptions D-08, S-04).
   ========================================================================= */
USE PULSE_DW;

DECLARE @dry  DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND is_rain_day = 0 AND data_split <> 'spill');
DECLARE @rain DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND is_rain_day = 1 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH banded AS (
    SELECT CASE WHEN t.hour_of_day BETWEEN 7 AND 10  THEN 1
                WHEN t.hour_of_day BETWEEN 11 AND 14 THEN 2
                WHEN t.hour_of_day BETWEEN 15 AND 16 THEN 3
                WHEN t.hour_of_day BETWEEN 17 AND 20 THEN 4
                ELSE 5 END AS band,
           t.is_rain_day, p.work_hours, p.supply_hours, p.lost_rides + p.lost_orders AS lost
    FROM dw.Agg_Pressure_ZoneHour p
    JOIN dw.Dim_Time t ON t.time_key = p.time_key
    WHERE t.is_weekend = 0
)
SELECT CASE band WHEN 1 THEN '1 Morning 07-10' WHEN 2 THEN '2 Midday 11-14' WHEN 3 THEN '3 Afternoon 15-16'
                 WHEN 4 THEN '4 Evening 17-20' ELSE '5 Night 21-06' END                     AS [Time band],
       CAST(SUM(CASE WHEN is_rain_day = 0 THEN work_hours END)
            / NULLIF(SUM(CASE WHEN is_rain_day = 0 THEN supply_hours END), 0) AS DECIMAL(6,2)) AS [City MPI dry],
       CAST(SUM(CASE WHEN is_rain_day = 1 THEN work_hours END)
            / NULLIF(SUM(CASE WHEN is_rain_day = 1 THEN supply_hours END), 0) AS DECIMAL(6,2)) AS [City MPI rain],
       CAST(SUM(CASE WHEN is_rain_day = 0 THEN lost ELSE 0 END) / @dry  AS DECIMAL(8,1))    AS [Lost per dry weekday],
       CAST(SUM(CASE WHEN is_rain_day = 1 THEN lost ELSE 0 END) / @rain AS DECIMAL(8,1))    AS [Lost per rain weekday]
FROM banded
GROUP BY band
ORDER BY band;

/* ---- Result Set B ------------------------------------------------------- */
SELECT z.zone_type                                                                           AS [Zone type],
       CAST(100.0 * SUM(CASE WHEN t.is_rain_day = 0 AND p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN t.is_rain_day = 0 AND p.pressure_state <> 'No activity' THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1)) AS [Under-supplied hours % dry],
       CAST(100.0 * SUM(CASE WHEN t.is_rain_day = 1 AND p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN t.is_rain_day = 1 AND p.pressure_state <> 'No activity' THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1)) AS [Under-supplied hours % rain],
       CAST(SUM(CASE WHEN t.is_rain_day = 0 THEN p.lost_rides + p.lost_orders ELSE 0 END) / @dry  AS DECIMAL(8,1)) AS [Lost per dry weekday],
       CAST(SUM(CASE WHEN t.is_rain_day = 1 THEN p.lost_rides + p.lost_orders ELSE 0 END) / @rain AS DECIMAL(8,1)) AS [Lost per rain weekday]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
WHERE t.is_weekend = 0
GROUP BY z.zone_type
ORDER BY [Under-supplied hours % rain] DESC;
