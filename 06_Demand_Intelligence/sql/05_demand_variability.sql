/* =========================================================================
   PULSE Phase 6 - 05: Demand growth and variability
   Result Set A: weekly demand with week-over-week change
   Result Set B: rain sensitivity by zone type (weekdays only)
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH wk AS (
    SELECT t.week_number, MIN(t.data_split) AS data_split,
           SUM(CASE WHEN m.service_key = 1 THEN m.demand ELSE 0 END) AS rides,
           SUM(CASE WHEN m.service_key = 2 THEN m.demand ELSE 0 END) AS orders
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.data_split <> 'spill'
    GROUP BY t.week_number
),
rain AS (
    SELECT week_number, COUNT(DISTINCT CASE WHEN is_rain_day = 1 THEN date_value END) AS rain_days
    FROM dw.Dim_Time WHERE data_split <> 'spill' GROUP BY week_number
)
SELECT w.week_number                                                                     AS [Week],
       w.data_split                                                                      AS [Split],
       r.rain_days                                                                       AS [Rain days],
       w.rides                                                                           AS [Ride requests],
       w.orders                                                                          AS [Food orders],
       CAST(100.0 * (w.rides  - LAG(w.rides)  OVER (ORDER BY w.week_number))
            / LAG(w.rides)  OVER (ORDER BY w.week_number) AS DECIMAL(5,1))               AS [Rides WoW %],
       CAST(100.0 * (w.orders - LAG(w.orders) OVER (ORDER BY w.week_number))
            / LAG(w.orders) OVER (ORDER BY w.week_number) AS DECIMAL(5,1))               AS [Food WoW %]
FROM wk w
JOIN rain r ON r.week_number = w.week_number
ORDER BY w.week_number;

/* ---- Result Set B ------------------------------------------------------- */
WITH daily AS (
    SELECT z.zone_type, t.date_value, t.is_rain_day,
           SUM(CASE WHEN m.service_key = 1 THEN m.demand ELSE 0 END) AS rides,
           SUM(CASE WHEN m.service_key = 2 THEN m.demand ELSE 0 END) AS orders
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    JOIN dw.Dim_Zone z ON z.zone_key = m.zone_key
    WHERE t.is_weekend = 0 AND t.data_split <> 'spill'
    GROUP BY z.zone_type, t.date_value, t.is_rain_day
),
agg AS (
    SELECT zone_type,
           AVG(CASE WHEN is_rain_day = 0 THEN CAST(rides  AS DECIMAL(12,2)) END) AS rides_dry,
           AVG(CASE WHEN is_rain_day = 1 THEN CAST(rides  AS DECIMAL(12,2)) END) AS rides_rain,
           AVG(CASE WHEN is_rain_day = 0 THEN CAST(orders AS DECIMAL(12,2)) END) AS orders_dry,
           AVG(CASE WHEN is_rain_day = 1 THEN CAST(orders AS DECIMAL(12,2)) END) AS orders_rain
    FROM daily GROUP BY zone_type
)
SELECT zone_type                                                              AS [Zone type],
       CAST(rides_dry   AS DECIMAL(8,0))                                      AS [Rides per dry weekday],
       CAST(rides_rain  AS DECIMAL(8,0))                                      AS [Rides per rain weekday],
       CAST(100.0 * (rides_rain - rides_dry) / rides_dry AS DECIMAL(5,1))     AS [Rain effect on rides %],
       CAST(orders_dry  AS DECIMAL(8,0))                                      AS [Orders per dry weekday],
       CAST(orders_rain AS DECIMAL(8,0))                                      AS [Orders per rain weekday],
       CAST(100.0 * (orders_rain - orders_dry) / orders_dry AS DECIMAL(5,1))  AS [Rain effect on food %]
FROM agg
ORDER BY [Rain effect on food %] DESC;
