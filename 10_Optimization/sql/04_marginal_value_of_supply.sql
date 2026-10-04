/* =========================================================================
   PULSE Phase 10 - 04: What is one more partner worth — where and when?
   LP shadow prices of the supply constraint (Stage 4 method), profit policy,
   weekday hours of the holdout weeks. INR per extra partner for that hour.
   Result Set A: the 15 most valuable weekday zone-hours for a two-wheeler
   Result Set B: by zone — average value and hours worth more than INR 20
   Feeds Phase 11: where incentives could bring partners online.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split = 'holdout' AND is_weekend = 0);

/* ---- Result Set A ------------------------------------------------------- */
SELECT TOP (15)
       z.zone_code                                                          AS [Zone],
       z.zone_type                                                          AS [Zone type],
       t.hour_of_day                                                        AS [Hour],
       CAST(SUM(v.shadow_price) / @weekdays AS DECIMAL(8,1))                AS [Avg value of one more two-wheeler (INR)],
       COUNT(*)                                                             AS [Weekdays with positive value]
FROM dw.Agg_Supply_Value v
JOIN dw.Dim_Time t ON t.time_key = v.time_key
JOIN dw.Dim_Zone z ON z.zone_key = v.zone_key
WHERE v.scenario_code = 'optimizer_profit' AND v.vehicle_key = 1 AND t.is_weekend = 0
GROUP BY z.zone_code, z.zone_type, t.hour_of_day
ORDER BY SUM(v.shadow_price) DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH zh AS (
    SELECT v.zone_key, t.hour_of_day, v.vehicle_key, SUM(v.shadow_price) / @weekdays AS avg_value
    FROM dw.Agg_Supply_Value v
    JOIN dw.Dim_Time t ON t.time_key = v.time_key
    WHERE v.scenario_code = 'optimizer_profit' AND t.is_weekend = 0
    GROUP BY v.zone_key, t.hour_of_day, v.vehicle_key
)
SELECT z.zone_code                                                                                  AS [Zone],
       z.zone_type                                                                                  AS [Zone type],
       CAST(SUM(CASE WHEN zh.vehicle_key = 1 THEN zh.avg_value ELSE 0 END) / 24 AS DECIMAL(8,1))  AS [Two-wheeler: avg value per hour (INR)],
       SUM(CASE WHEN zh.vehicle_key = 1 AND zh.avg_value > 20 THEN 1 ELSE 0 END)                  AS [Two-wheeler: hours worth > INR 20],
       CAST(SUM(CASE WHEN zh.vehicle_key = 2 THEN zh.avg_value ELSE 0 END) / 24 AS DECIMAL(8,1))  AS [Cab: avg value per hour (INR)],
       SUM(CASE WHEN zh.vehicle_key = 2 AND zh.avg_value > 20 THEN 1 ELSE 0 END)                  AS [Cab: hours worth > INR 20]
FROM dw.Dim_Zone z
LEFT JOIN zh ON zh.zone_key = z.zone_key
GROUP BY z.zone_code, z.zone_type
ORDER BY [Two-wheeler: avg value per hour (INR)] DESC;
