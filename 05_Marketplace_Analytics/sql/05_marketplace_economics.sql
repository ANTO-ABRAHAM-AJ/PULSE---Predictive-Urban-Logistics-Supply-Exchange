/* =========================================================================
   PULSE Phase 5 - 05: Marketplace economics
   Result Set A: gross value -> partner payout -> platform revenue -> contribution
   Result Set B: weekly trend (history and holdout weeks)
   Note: status-quo history has no incentives or repositioning, so
   contribution = platform revenue here (KPI_Dictionary.md section 5).
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
SELECT [Service], [Completed jobs], [Gross value (INR)], [Partner payout (INR)],
       [Platform revenue (INR)], [Take rate %], [Incentives + repositioning (INR)],
       [Contribution (INR)], [Contribution per job (INR)], [Share of contribution %]
FROM (
    SELECT m.service_key                                                      AS sort_key,
           s.service_name                                                     AS [Service],
           SUM(m.completed)                                                   AS [Completed jobs],
           CAST(SUM(m.gross_value)      AS DECIMAL(14,0))                     AS [Gross value (INR)],
           CAST(SUM(m.partner_payout)   AS DECIMAL(14,0))                     AS [Partner payout (INR)],
           CAST(SUM(m.platform_revenue) AS DECIMAL(14,0))                     AS [Platform revenue (INR)],
           CAST(100.0 * SUM(m.platform_revenue) / SUM(m.gross_value) AS DECIMAL(5,1)) AS [Take rate %],
           CAST(0 AS DECIMAL(14,0))                                           AS [Incentives + repositioning (INR)],
           CAST(SUM(m.platform_revenue) AS DECIMAL(14,0))                     AS [Contribution (INR)],
           CAST(SUM(m.platform_revenue) / SUM(m.completed) AS DECIMAL(10,2))  AS [Contribution per job (INR)],
           CAST(100.0 * SUM(m.platform_revenue)
                / (SELECT SUM(platform_revenue) FROM dw.vw_Marketplace_ZoneHour) AS DECIMAL(5,1)) AS [Share of contribution %]
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Service s ON s.service_key = m.service_key
    GROUP BY m.service_key, s.service_name
    UNION ALL
    SELECT 9, 'Marketplace total', SUM(completed),
           CAST(SUM(gross_value) AS DECIMAL(14,0)), CAST(SUM(partner_payout) AS DECIMAL(14,0)),
           CAST(SUM(platform_revenue) AS DECIMAL(14,0)),
           CAST(100.0 * SUM(platform_revenue) / SUM(gross_value) AS DECIMAL(5,1)),
           CAST(0 AS DECIMAL(14,0)),
           CAST(SUM(platform_revenue) AS DECIMAL(14,0)),
           CAST(SUM(platform_revenue) / SUM(completed) AS DECIMAL(10,2)),
           CAST(100.0 AS DECIMAL(5,1))
    FROM dw.vw_Marketplace_ZoneHour
) e
ORDER BY sort_key;

/* ---- Result Set B ------------------------------------------------------- */
WITH weekly AS (
    SELECT t.week_number,
           MIN(t.data_split) AS data_split,
           SUM(CASE WHEN m.service_key = 1 THEN m.completed ELSE 0 END)        AS rides_completed,
           SUM(CASE WHEN m.service_key = 2 THEN m.completed ELSE 0 END)        AS orders_delivered,
           SUM(m.demand)                                                       AS demand,
           SUM(m.completed)                                                    AS completed,
           SUM(m.platform_revenue)                                             AS platform_revenue
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Time t ON t.time_key = m.time_key
    WHERE t.data_split <> 'spill'
    GROUP BY t.week_number
),
rain AS (
    SELECT week_number, COUNT(DISTINCT CASE WHEN is_rain_day = 1 THEN date_value END) AS rain_days
    FROM dw.Dim_Time
    WHERE data_split <> 'spill'
    GROUP BY week_number
)
SELECT w.week_number                                                 AS [Week],
       w.data_split                                                  AS [Split],
       r.rain_days                                                   AS [Rain days],
       w.rides_completed                                             AS [Rides completed],
       w.orders_delivered                                            AS [Orders delivered],
       CAST(100.0 * w.completed / w.demand AS DECIMAL(5,1))          AS [Fulfilment %],
       CAST(w.platform_revenue AS DECIMAL(14,0))                     AS [Contribution (INR)]
FROM weekly w
JOIN rain r ON r.week_number = w.week_number
ORDER BY w.week_number;
