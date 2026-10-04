/* =========================================================================
   PULSE Phase 10 - 01: Status quo vs optimized repositioning (holdout weeks)
   Result Set A: outcome and economics by scenario
   Result Set B: completion by scenario and service
   Every scenario replays the same requests (common random numbers).
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH o AS (
    SELECT scenario_code, SUM(requests) AS requests, SUM(completed) AS completed,
           SUM(lost_no_partner) AS lost, SUM(revenue) AS revenue
    FROM dw.Agg_Policy_ZoneHour GROUP BY scenario_code
),
c AS (
    SELECT scenario_code, COUNT(*) AS moves, SUM(reposition_cost) AS cost
    FROM dw.Fact_Repositioning GROUP BY scenario_code
),
x AS (
    SELECT o.scenario_code, o.requests, o.completed, o.lost, o.revenue,
           ISNULL(c.moves, 0) AS moves, ISNULL(c.cost, 0) AS cost,
           o.revenue - ISNULL(c.cost, 0) AS contribution
    FROM o LEFT JOIN c ON c.scenario_code = o.scenario_code
)
SELECT x.scenario_code                                                              AS [Scenario],
       x.completed                                                                  AS [Completed jobs],
       x.lost                                                                       AS [Jobs lost to no partner],
       CAST(100.0 * (x.lost - b.lost) / b.lost AS DECIMAL(6,1))                     AS [Lost jobs change %],
       x.moves                                                                      AS [Repositioning moves],
       CAST(x.revenue AS DECIMAL(14,0))                                             AS [Platform revenue (INR)],
       CAST(x.cost AS DECIMAL(14,0))                                                AS [Repositioning cost (INR)],
       CAST(x.contribution AS DECIMAL(14,0))                                        AS [Contribution (INR)],
       CAST(100.0 * (x.contribution - b.contribution) / b.contribution AS DECIMAL(6,2)) AS [Contribution change %]
FROM x
CROSS JOIN (SELECT lost, contribution FROM x WHERE scenario_code = 'status_quo') b
ORDER BY CASE x.scenario_code WHEN 'status_quo' THEN 0 WHEN 'optimizer_profit' THEN 1
                              WHEN 'optimizer_service' THEN 2 ELSE 3 END;

/* ---- Result Set B ------------------------------------------------------- */
SELECT p.scenario_code                                                              AS [Scenario],
       s.service_name                                                               AS [Service],
       SUM(p.requests)                                                              AS [Requests],
       CAST(100.0 * SUM(p.completed) / SUM(p.requests) AS DECIMAL(5,1))             AS [Completion %],
       CAST(100.0 * SUM(p.lost_no_partner) / SUM(p.requests) AS DECIMAL(5,1))       AS [Lost to no partner %],
       CAST(100.0 * SUM(p.cancelled_customer) / SUM(p.requests) AS DECIMAL(5,1))    AS [Customer cancel %]
FROM dw.Agg_Policy_ZoneHour p
JOIN dw.Dim_Service s ON s.service_key = p.service_key
GROUP BY p.scenario_code, s.service_key, s.service_name
ORDER BY s.service_key,
         CASE p.scenario_code WHEN 'status_quo' THEN 0 WHEN 'optimizer_profit' THEN 1
                              WHEN 'optimizer_service' THEN 2 ELSE 3 END;
