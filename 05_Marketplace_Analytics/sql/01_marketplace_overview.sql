/* =========================================================================
   PULSE Phase 5 - 01: Marketplace overview
   Result Set A: demand, fulfilment and revenue by service (+ total)
   Result Set B: supply volume and utilization by vehicle type (+ total)
   ========================================================================= */
USE PULSE_DW;

DECLARE @days DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split <> 'spill');
DECLARE @hours DECIMAL(10,2) = @days * 24;

/* ---- Result Set A ------------------------------------------------------- */
SELECT [Service], [Demand], [Demand per day], [Completed], [Completion %],
       [Lost: no partner %], [Platform revenue (INR)], [Revenue per completed job (INR)]
FROM (
    SELECT s.service_key                                                   AS sort_key,
           s.service_name                                                  AS [Service],
           SUM(m.demand)                                                   AS [Demand],
           CAST(SUM(m.demand) / @days AS DECIMAL(12,0))                    AS [Demand per day],
           SUM(m.completed)                                                AS [Completed],
           CAST(100.0 * SUM(m.completed)       / SUM(m.demand) AS DECIMAL(5,1)) AS [Completion %],
           CAST(100.0 * SUM(m.lost_no_partner) / SUM(m.demand) AS DECIMAL(5,1)) AS [Lost: no partner %],
           CAST(SUM(m.platform_revenue) AS DECIMAL(14,0))                  AS [Platform revenue (INR)],
           CAST(SUM(m.platform_revenue) / NULLIF(SUM(m.completed), 0) AS DECIMAL(10,2)) AS [Revenue per completed job (INR)]
    FROM dw.vw_Marketplace_ZoneHour m
    JOIN dw.Dim_Service s ON s.service_key = m.service_key
    GROUP BY s.service_key, s.service_name
    UNION ALL
    SELECT 9, 'Marketplace total',
           SUM(demand), CAST(SUM(demand) / @days AS DECIMAL(12,0)), SUM(completed),
           CAST(100.0 * SUM(completed)       / SUM(demand) AS DECIMAL(5,1)),
           CAST(100.0 * SUM(lost_no_partner) / SUM(demand) AS DECIMAL(5,1)),
           CAST(SUM(platform_revenue) AS DECIMAL(14,0)),
           CAST(SUM(platform_revenue) / NULLIF(SUM(completed), 0) AS DECIMAL(10,2))
    FROM dw.vw_Marketplace_ZoneHour
) a
ORDER BY sort_key;

/* ---- Result Set B ------------------------------------------------------- */
SELECT [Vehicle], [Online partner-hours], [Avg partners online per hour],
       [Utilization %], [Idle hours], [Empty km per busy hour]
FROM (
    SELECT v.vehicle_key                                                  AS sort_key,
           v.vehicle_name                                                 AS [Vehicle],
           SUM(x.partner_hours)                                           AS [Online partner-hours],
           CAST(SUM(x.online_hours) / @hours AS DECIMAL(8,1))             AS [Avg partners online per hour],
           CAST(100.0 * SUM(x.busy_hours) / SUM(x.online_hours) AS DECIMAL(5,1)) AS [Utilization %],
           CAST(SUM(x.idle_hours) AS DECIMAL(12,0))                       AS [Idle hours],
           CAST(SUM(x.empty_km) / NULLIF(SUM(x.busy_hours), 0) AS DECIMAL(8,2))  AS [Empty km per busy hour]
    FROM dw.vw_Supply_ZoneHour x
    JOIN dw.Dim_Vehicle v ON v.vehicle_key = x.vehicle_key
    GROUP BY v.vehicle_key, v.vehicle_name
    UNION ALL
    SELECT 9, 'All partners',
           SUM(partner_hours),
           CAST(SUM(online_hours) / @hours AS DECIMAL(8,1)),
           CAST(100.0 * SUM(busy_hours) / SUM(online_hours) AS DECIMAL(5,1)),
           CAST(SUM(idle_hours) AS DECIMAL(12,0)),
           CAST(SUM(empty_km) / NULLIF(SUM(busy_hours), 0) AS DECIMAL(8,2))
    FROM dw.vw_Supply_ZoneHour
) b
ORDER BY sort_key;
