/* =========================================================================
   PULSE Phase 5 - 03: Food delivery performance
   Result Set A: food KPIs by customer zone type
   Result Set B: weekday hour-of-day profile
   ========================================================================= */
USE PULSE_DW;

DECLARE @weekdays DECIMAL(10,2) =
    (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE is_weekend = 0 AND data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
SELECT z.zone_type                                                              AS [Zone type],
       SUM(f.food_orders)                                                       AS [Orders],
       CAST(100.0 * SUM(f.delivered_orders)     / SUM(f.food_orders) AS DECIMAL(5,1)) AS [Delivered %],
       CAST(100.0 * SUM(f.cancelled_no_partner) / SUM(f.food_orders) AS DECIMAL(5,1)) AS [No partner %],
       CAST(100.0 * SUM(f.cancelled_restaurant) / SUM(f.food_orders) AS DECIMAL(5,1)) AS [Restaurant reject %],
       CAST(SUM(f.prep_min_sum)          / NULLIF(SUM(f.delivered_orders), 0) AS DECIMAL(5,1)) AS [Avg prep (min)],
       CAST(SUM(f.order_to_door_min_sum) / NULLIF(SUM(f.delivered_orders), 0) AS DECIMAL(5,1)) AS [Avg order-to-door (min)],
       CAST(SUM(f.gmv) / NULLIF(SUM(f.delivered_orders), 0) AS DECIMAL(8,0))   AS [AOV (INR)],
       CAST(SUM(f.platform_revenue) AS DECIMAL(14,0))                           AS [Platform revenue (INR)]
FROM dw.vw_Food_ZoneHour f
JOIN dw.Dim_Zone z ON z.zone_key = f.zone_key
GROUP BY z.zone_type
ORDER BY [Delivered %];

/* ---- Result Set B ------------------------------------------------------- */
SELECT t.hour_of_day                                                            AS [Hour],
       CAST(SUM(f.food_orders) / @weekdays AS DECIMAL(8,0))                     AS [Orders per weekday],
       CAST(100.0 * SUM(f.delivered_orders) / SUM(f.food_orders) AS DECIMAL(5,1)) AS [Delivered %],
       CAST(SUM(f.cancelled_no_partner) / @weekdays AS DECIMAL(8,1))            AS [Lost to no partner per weekday],
       CAST(SUM(f.order_to_door_min_sum) / NULLIF(SUM(f.delivered_orders), 0) AS DECIMAL(5,1)) AS [Avg order-to-door (min)]
FROM dw.vw_Food_ZoneHour f
JOIN dw.Dim_Time t ON t.time_key = f.time_key
WHERE t.is_weekend = 0
GROUP BY t.hour_of_day
ORDER BY t.hour_of_day;
