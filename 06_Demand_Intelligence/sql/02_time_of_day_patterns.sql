/* =========================================================================
   PULSE Phase 6 - 02: Time-of-day demand patterns by zone type
   Result Set A: weekday rides per zone, by hour and zone type
   Result Set B: weekday food orders per zone, by hour and zone type
   Values are per ZONE (divided by the number of zones of each type), so
   zone types of different sizes can be compared on shape.
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH typed AS (
    SELECT t.hour_of_day, z.zone_type, SUM(m.demand) / @weekdays
           / (SELECT COUNT(*) FROM dw.Dim_Zone zz WHERE zz.zone_type = z.zone_type) AS per_zone
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill' AND m.service_key = 1
    GROUP BY t.hour_of_day, z.zone_type
)
SELECT hour_of_day                                                                          AS [Hour],
       CAST(SUM(CASE WHEN zone_type = 'office'             THEN per_zone END) AS DECIMAL(7,1)) AS [Office],
       CAST(SUM(CASE WHEN zone_type = 'residential'        THEN per_zone END) AS DECIMAL(7,1)) AS [Residential],
       CAST(SUM(CASE WHEN zone_type = 'mixed'              THEN per_zone END) AS DECIMAL(7,1)) AS [Mixed],
       CAST(SUM(CASE WHEN zone_type = 'restaurant_cluster' THEN per_zone END) AS DECIMAL(7,1)) AS [Restaurant cluster],
       CAST(SUM(CASE WHEN zone_type = 'transit_hub'        THEN per_zone END) AS DECIMAL(7,1)) AS [Transit hub]
FROM typed
GROUP BY hour_of_day
ORDER BY hour_of_day;

/* ---- Result Set B ------------------------------------------------------- */
WITH typed AS (
    SELECT t.hour_of_day, z.zone_type, SUM(m.demand) / @weekdays
           / (SELECT COUNT(*) FROM dw.Dim_Zone zz WHERE zz.zone_type = z.zone_type) AS per_zone
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill' AND m.service_key = 2
    GROUP BY t.hour_of_day, z.zone_type
)
SELECT hour_of_day                                                                          AS [Hour],
       CAST(SUM(CASE WHEN zone_type = 'office'             THEN per_zone END) AS DECIMAL(7,1)) AS [Office],
       CAST(SUM(CASE WHEN zone_type = 'residential'        THEN per_zone END) AS DECIMAL(7,1)) AS [Residential],
       CAST(SUM(CASE WHEN zone_type = 'mixed'              THEN per_zone END) AS DECIMAL(7,1)) AS [Mixed],
       CAST(SUM(CASE WHEN zone_type = 'restaurant_cluster' THEN per_zone END) AS DECIMAL(7,1)) AS [Restaurant cluster],
       CAST(SUM(CASE WHEN zone_type = 'transit_hub'        THEN per_zone END) AS DECIMAL(7,1)) AS [Transit hub]
FROM typed
GROUP BY hour_of_day
ORDER BY hour_of_day;
