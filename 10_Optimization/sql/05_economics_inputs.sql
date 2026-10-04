/* PULSE Phase 10 - 05: optimizer economics from the warehouse (resolves X-02).
   Platform revenue per completed job, history weeks only (never the holdout). */
USE PULSE_DW;

SELECT s.service_code                                                              AS service_code,
       s.service_name                                                              AS [Service],
       SUM(m.completed)                                                            AS [Completed jobs (history)],
       CAST(SUM(m.platform_revenue) AS DECIMAL(14,0))                              AS [Platform revenue (INR)],
       CAST(SUM(m.platform_revenue) / NULLIF(SUM(m.completed), 0) AS DECIMAL(8,2)) AS [Contribution per job (INR)]
FROM dw.vw_Marketplace_ZoneHour m
JOIN dw.Dim_Time t    ON t.time_key = m.time_key
JOIN dw.Dim_Service s ON s.service_key = m.service_key
WHERE t.data_split = 'history'
GROUP BY s.service_key, s.service_code, s.service_name
ORDER BY s.service_key;
