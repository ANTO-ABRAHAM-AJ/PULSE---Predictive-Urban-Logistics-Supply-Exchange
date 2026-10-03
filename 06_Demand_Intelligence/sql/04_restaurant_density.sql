/* =========================================================================
   PULSE Phase 6 - 04: Restaurant density and food demand
   Result Set A: restaurants, orders and delivery performance per zone
   Result Set B: how concentrated orders are across restaurants (deciles)
   ========================================================================= */
USE PULSE_DW;

DECLARE @days DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split <> 'spill');

/* ---- Result Set A ------------------------------------------------------- */
WITH rest AS (
    SELECT zone_key, COUNT(*) AS restaurants FROM dw.Dim_Restaurant GROUP BY zone_key
),
ord AS (
    SELECT o.customer_zone_key AS zone_key,
           COUNT(*) AS orders,
           SUM(CASE WHEN o.restaurant_zone_key = o.customer_zone_key THEN 1 ELSE 0 END) AS own_zone,
           SUM(CAST(o.is_delivered AS INT)) AS delivered,
           SUM(CASE WHEN o.is_delivered = 1 THEN o.delivery_minutes ELSE 0 END) AS door_min
    FROM dw.Fact_Food_Orders o
    GROUP BY o.customer_zone_key
),
supplied AS (                  -- orders each zone's restaurants prepared (for anyone)
    SELECT restaurant_zone_key AS zone_key, COUNT(*) AS prepared
    FROM dw.Fact_Food_Orders GROUP BY restaurant_zone_key
)
SELECT z.zone_code                                                              AS [Zone],
       z.zone_type                                                              AS [Zone type],
       ISNULL(r.restaurants, 0)                                                 AS [Restaurants],
       CAST(o.orders / @days AS DECIMAL(8,0))                                   AS [Orders per day],
       CAST(ISNULL(sp.prepared, 0) / @days / NULLIF(r.restaurants, 0) AS DECIMAL(6,1)) AS [Orders per restaurant per day],
       CAST(100.0 * o.own_zone / o.orders AS DECIMAL(5,1))                      AS [Ordered from own zone %],
       CAST(100.0 * o.delivered / o.orders AS DECIMAL(5,1))                     AS [Delivered %],
       CAST(o.door_min / NULLIF(o.delivered, 0) AS DECIMAL(5,1))                AS [Avg order-to-door (min)]
FROM ord o
JOIN dw.Dim_Zone z       ON z.zone_key = o.zone_key
LEFT JOIN rest r         ON r.zone_key = o.zone_key
LEFT JOIN supplied sp    ON sp.zone_key = o.zone_key
ORDER BY [Restaurants] DESC, [Orders per day] DESC;

/* ---- Result Set B ------------------------------------------------------- */
WITH per_rest AS (
    SELECT r.restaurant_key, COUNT(o.order_key) AS orders
    FROM dw.Dim_Restaurant r
    LEFT JOIN dw.Fact_Food_Orders o ON o.restaurant_key = r.restaurant_key
    GROUP BY r.restaurant_key
),
ranked AS (
    SELECT orders, NTILE(10) OVER (ORDER BY orders DESC) AS decile FROM per_rest
),
dec AS (
    SELECT decile, COUNT(*) AS restaurants, SUM(orders) AS orders FROM ranked GROUP BY decile
)
SELECT decile                                                                   AS [Restaurant decile (1 = busiest)],
       restaurants                                                              AS [Restaurants],
       orders                                                                   AS [Orders],
       CAST(100.0 * orders / SUM(orders) OVER () AS DECIMAL(5,1))               AS [Share of orders %],
       CAST(100.0 * SUM(orders) OVER (ORDER BY decile ROWS UNBOUNDED PRECEDING)
            / SUM(orders) OVER () AS DECIMAL(5,1))                              AS [Cumulative share %]
FROM dec
ORDER BY decile;
