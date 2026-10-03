/* =========================================================================
   PULSE Phase 8 - 02: Where and when is the marketplace under pressure?
   Result Set A: per zone — share of weekday hours under / over supplied,
                 pressure in the morning and evening peaks
   Result Set B: per weekday hour — city MPI and how many zones are short
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
SELECT z.zone_code                                                                    AS [Zone],
       z.zone_type                                                                    AS [Zone type],
       CAST(100.0 * SUM(CASE WHEN p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN p.pressure_state <> 'No activity' THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1)) AS [Under-supplied hours %],
       CAST(100.0 * SUM(CASE WHEN p.pressure_state = 'Over-supplied' THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN p.pressure_state <> 'No activity' THEN 1 ELSE 0 END), 0) AS DECIMAL(5,1)) AS [Over-supplied hours %],
       CAST(SUM(CASE WHEN t.hour_of_day BETWEEN 8 AND 10 THEN p.work_hours END)
            / NULLIF(SUM(CASE WHEN t.hour_of_day BETWEEN 8 AND 10 THEN p.supply_hours END), 0) AS DECIMAL(6,2)) AS [MPI 08-10],
       CAST(SUM(CASE WHEN t.hour_of_day BETWEEN 17 AND 20 THEN p.work_hours END)
            / NULLIF(SUM(CASE WHEN t.hour_of_day BETWEEN 17 AND 20 THEN p.supply_hours END), 0) AS DECIMAL(6,2)) AS [MPI 17-20],
       CAST(SUM(p.lost_rides + p.lost_orders) / @weekdays AS DECIMAL(8,1))            AS [Jobs lost per weekday]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
JOIN dw.Dim_Zone z ON z.zone_key = p.zone_key
WHERE t.is_weekend = 0
GROUP BY z.zone_code, z.zone_type
ORDER BY [Under-supplied hours %] DESC;

/* ---- Result Set B ------------------------------------------------------- */
SELECT t.hour_of_day                                                                   AS [Hour],
       CAST(SUM(p.work_hours) / NULLIF(SUM(p.supply_hours), 0) AS DECIMAL(6,2))        AS [City MPI],
       CAST(SUM(CASE WHEN p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END) / @weekdays AS DECIMAL(5,1)) AS [Zones under-supplied],
       CAST(SUM(CASE WHEN p.pressure_state = 'Balanced' THEN 1 ELSE 0 END) / @weekdays AS DECIMAL(5,1))       AS [Zones balanced],
       CAST(SUM(CASE WHEN p.pressure_state = 'Over-supplied' THEN 1 ELSE 0 END) / @weekdays AS DECIMAL(5,1))  AS [Zones over-supplied],
       CAST(SUM(p.lost_rides + p.lost_orders) / @weekdays AS DECIMAL(8,0))                                    AS [Jobs lost per weekday]
FROM dw.Agg_Pressure_ZoneHour p
JOIN dw.Dim_Time t ON t.time_key = p.time_key
WHERE t.is_weekend = 0
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;
