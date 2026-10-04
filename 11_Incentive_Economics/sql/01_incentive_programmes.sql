/* =========================================================================
   PULSE Phase 11 - 01: Do incentive programmes pay? (holdout weeks)
   Result Set A: each programme vs the profit repositioning policy
   Result Set B: the INR 40 programme by zone — return per rupee
   Programmes add guaranteed-hour two-wheeler partners in zone-hours chosen
   from VALIDATION shadow prices; every scenario replays the same customers.
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH s AS (SELECT * FROM dw.Agg_Scenario_Summary WHERE study = 'incentive'),
p AS (SELECT * FROM s WHERE scenario_code = 'optimizer_profit'),
q AS (SELECT * FROM s WHERE scenario_code = 'status_quo')
SELECT s.scenario_code                                                                     AS [Scenario],
       CAST(s.bonus AS DECIMAL(6,0))                                                       AS [Bonus per partner-hour (INR)],
       s.incentive_partner_hours                                                           AS [Partner-hours bought per weekday],
       CAST(s.incentive_cost / s.days AS DECIMAL(10,0))                                    AS [Incentive cost per day (INR)],
       CAST((s.revenue - p.revenue) / s.days AS DECIMAL(10,0))                             AS [Revenue gain per day (INR)],
       CAST((s.contribution - p.contribution) / s.days AS DECIMAL(10,0))                   AS [Net vs profit policy per day (INR)],
       s.lost_no_partner                                                                   AS [Jobs lost],
       CAST(100.0 * (s.lost_no_partner - q.lost_no_partner) / q.lost_no_partner AS DECIMAL(6,1)) AS [Lost jobs change vs status quo %],
       CAST((p.lost_no_partner - s.lost_no_partner) * 1.0 / s.days AS DECIMAL(8,0))        AS [Extra jobs per day vs profit policy],
       CAST(CASE WHEN s.bonus > 0 THEN (p.contribution - s.contribution)
                 / NULLIF(p.lost_no_partner - s.lost_no_partner, 0) END AS DECIMAL(8,1)) AS [Net cost per extra job (INR)]
FROM s CROSS JOIN p CROSS JOIN q
ORDER BY s.bonus, s.scenario_code DESC;

/* ---- Result Set B ------------------------------------------------------- */
DECLARE @days DECIMAL(10,2) = (SELECT COUNT(DISTINCT date_value) FROM dw.Dim_Time WHERE data_split = 'holdout');

WITH rev AS (
    SELECT zone_key,
           SUM(CASE WHEN scenario_code = 'incentive_40'     THEN revenue ELSE 0 END) AS inc,
           SUM(CASE WHEN scenario_code = 'optimizer_profit' THEN revenue ELSE 0 END) AS base
    FROM dw.Agg_Policy_ZoneHour
    WHERE scenario_code IN ('incentive_40', 'optimizer_profit')
    GROUP BY zone_key
),
cost AS (
    SELECT zone_key, SUM(extra_partner_hours) AS ph, SUM(incentive_amount) AS cost
    FROM dw.Fact_Incentives WHERE scenario_code = 'incentive_40'
    GROUP BY zone_key
)
SELECT z.zone_code                                                              AS [Zone],
       z.zone_type                                                              AS [Zone type],
       CAST(c.ph / @days AS DECIMAL(8,1))                                       AS [Partner-hours per day],
       CAST(c.cost / @days AS DECIMAL(10,0))                                    AS [Incentive cost per day (INR)],
       CAST((r.inc - r.base) / @days AS DECIMAL(10,0))                          AS [Revenue gain per day (INR)],
       CAST((r.inc - r.base) / NULLIF(c.cost, 0) AS DECIMAL(6,2))               AS [Revenue per rupee of incentive]
FROM cost c
JOIN rev r         ON r.zone_key = c.zone_key
JOIN dw.Dim_Zone z ON z.zone_key = c.zone_key
ORDER BY [Revenue per rupee of incentive] DESC;
