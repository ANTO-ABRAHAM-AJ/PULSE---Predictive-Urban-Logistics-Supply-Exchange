/* =========================================================================
   PULSE Phase 11 - 02: Stress scenarios (14 holdout days)
   Result Set A: every stress case under each policy
   Result Set B: per stress case — what repositioning and incentives recover,
                 and the bonus at which the incentive programme breaks even
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH s AS (SELECT * FROM dw.Agg_Scenario_Summary WHERE study = 'stress'),
n AS (SELECT * FROM s WHERE scenario_code = 'normal:status_quo')
SELECT s.stress_case                                                                      AS [Stress case],
       s.policy                                                                           AS [Policy],
       CAST(100.0 * s.completed / s.requests AS DECIMAL(5,1))                             AS [Completion %],
       CAST(s.lost_no_partner * 1.0 / s.days AS DECIMAL(8,0))                             AS [Lost jobs per day],
       CAST(s.contribution / s.days AS DECIMAL(12,0))                                     AS [Contribution per day (INR)],
       CAST(100.0 * (s.lost_no_partner - n.lost_no_partner) / n.lost_no_partner AS DECIMAL(6,1)) AS [Lost jobs vs normal status quo %]
FROM s CROSS JOIN n
ORDER BY CASE s.stress_case WHEN 'normal' THEN 0 ELSE 1 END, s.stress_case,
         CASE s.policy WHEN 'status_quo' THEN 0 WHEN 'profit' THEN 1 WHEN 'service' THEN 2 ELSE 3 END;

/* ---- Result Set B ------------------------------------------------------- */
WITH s AS (SELECT * FROM dw.Agg_Scenario_Summary WHERE study = 'stress'),
w AS (
    SELECT stress_case,
           MAX(CASE WHEN policy = 'status_quo'         THEN lost_no_partner END) AS sq_lost,
           MAX(CASE WHEN policy = 'profit'             THEN lost_no_partner END) AS pr_lost,
           MAX(CASE WHEN policy = 'service'            THEN lost_no_partner END) AS sv_lost,
           MAX(CASE WHEN policy = 'profit + incentive' THEN lost_no_partner END) AS in_lost,
           MAX(CASE WHEN policy = 'profit'             THEN revenue END)         AS pr_rev,
           MAX(CASE WHEN policy = 'profit + incentive' THEN revenue END)         AS in_rev,
           MAX(CASE WHEN policy = 'profit + incentive' THEN incentive_cost / NULLIF(bonus, 0) END) AS inc_hours,
           MAX(days) AS days
    FROM s GROUP BY stress_case
)
SELECT stress_case                                                                   AS [Stress case],
       CAST(100.0 * (sq_lost - pr_lost) / sq_lost AS DECIMAL(6,1))                   AS [Recovered by profit policy %],
       CAST(100.0 * (sq_lost - sv_lost) / sq_lost AS DECIMAL(6,1))                   AS [Recovered by service policy %],
       CAST((pr_lost - in_lost) * 1.0 / days AS DECIMAL(8,0))                         AS [Extra jobs per day from incentives],
       CAST((in_rev - pr_rev) / NULLIF(inc_hours, 0) AS DECIMAL(8,1))                AS [Break-even bonus per partner-hour (INR)]
FROM w
ORDER BY [Break-even bonus per partner-hour (INR)] DESC;
