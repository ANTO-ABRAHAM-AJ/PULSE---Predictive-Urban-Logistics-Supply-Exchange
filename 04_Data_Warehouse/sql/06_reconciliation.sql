/* =========================================================================
   PULSE Data Warehouse - 06: headline reconciliation
   Headline figures computed in SQL, to compare with the Python-generated
   results in 03_Data_Engineering/Generation_Results.md. They must agree.
   ========================================================================= */
USE PULSE_DW;

SELECT 'Ride requests' AS measure,
       CAST(COUNT(*) AS DECIMAL(18,2)) AS sql_value
FROM dw.Fact_Ride_Requests
UNION ALL
SELECT 'Ride completion rate (%)',
       CAST(100.0 * SUM(CAST(is_completed AS INT)) / COUNT(*) AS DECIMAL(18,2))
FROM dw.Fact_Ride_Requests
UNION ALL
SELECT 'Food orders', CAST(COUNT(*) AS DECIMAL(18,2))
FROM dw.Fact_Food_Orders
UNION ALL
SELECT 'Food delivery rate (%)',
       CAST(100.0 * SUM(CAST(is_delivered AS INT)) / COUNT(*) AS DECIMAL(18,2))
FROM dw.Fact_Food_Orders
UNION ALL
SELECT 'Average order value (INR)', CAST(AVG(order_value) AS DECIMAL(18,2))
FROM dw.Fact_Food_Orders
UNION ALL
SELECT 'Partner utilization (%)',
       CAST(100.0 * SUM(busy_minutes) / SUM(online_minutes) AS DECIMAL(18,2))
FROM dw.Fact_Driver_Availability
UNION ALL
SELECT 'Office-zone weekday 17-19 ride completion (%)',
       CAST(100.0 * SUM(CAST(r.is_completed AS INT)) / COUNT(*) AS DECIMAL(18,2))
FROM dw.Fact_Ride_Requests r
JOIN dw.Dim_Zone z ON z.zone_key = r.pickup_zone_key
JOIN dw.Dim_Time t ON t.time_key = r.time_key
WHERE z.zone_type = 'office' AND t.is_weekend = 0 AND t.hour_of_day BETWEEN 17 AND 19;
