/* =========================================================================
   PULSE Phase 12 - 01: Numbers every dashboard measure must reproduce
   Result Set A: one row per DAX check measure, computed in SQL from the
                 pbi views (same order as EVALUATE in PULSE_measures.dax)
   Result Set B: scenario economics from pbi.Fact_Scenario_Economics,
                 reconciling the Power BI layer to Phases 10-11
   Units: pct = percent (DAX shows 0.719 as 71.9%), inr = rupees,
          count = whole number, dec = decimal.
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH
mk AS (
    SELECT SUM(m.demand) AS demand, SUM(m.completed) AS completed, SUM(m.lost_no_partner) AS lost,
           SUM(m.platform_revenue) AS revenue,
           SUM(CASE WHEN m.service_key = 1 THEN m.completed END) * 1.0
             / SUM(CASE WHEN m.service_key = 1 THEN m.demand END)      AS ride_completion,
           SUM(CASE WHEN m.service_key = 2 THEN m.completed END) * 1.0
             / SUM(CASE WHEN m.service_key = 2 THEN m.demand END)      AS food_delivered
    FROM pbi.Fact_Marketplace m
),
dy AS (SELECT COUNT(DISTINCT date_value) AS days FROM pbi.Dim_Time WHERE data_split <> 'spill'),
sp AS (
    SELECT SUM(partner_hours) AS partner_hours, SUM(online_hours) AS online, SUM(busy_hours) AS busy,
           SUM(idle_hours) AS idle, SUM(empty_km) AS empty_km
    FROM pbi.Fact_Supply
),
pr AS (
    SELECT COUNT(*) AS zone_hours, SUM(is_under_supplied) AS under, SUM(lost_jobs) AS lost,
           SUM(CASE WHEN shortage_type = 'Reposition ahead'  THEN lost_jobs ELSE 0 END) AS lost_ahead,
           SUM(CASE WHEN shortage_type = 'Citywide shortage' THEN lost_jobs ELSE 0 END) AS lost_city
    FROM pbi.Fact_Pressure
),
fc AS (
    SELECT SUM(CASE WHEN model_name = 'GBM + rain'     THEN abs_error END)
             / SUM(CASE WHEN model_name = 'GBM + rain'     THEN actual_demand END) AS wape_gbm,
           SUM(CASE WHEN model_name = 'Seasonal naive' THEN abs_error END)
             / SUM(CASE WHEN model_name = 'Seasonal naive' THEN actual_demand END) AS wape_naive
    FROM pbi.Fact_Demand_Forecast
),
pf AS (
    SELECT SUM(predicted_short) * 1.0 / COUNT(*)                                        AS flag_rate,
           SUM(CASE WHEN predicted_short = 1 THEN lost_jobs ELSE 0 END) * 1.0 / SUM(lost_jobs) AS captured
    FROM pbi.Fact_Pressure_Forecast
),
se AS (SELECT * FROM pbi.Fact_Scenario_Economics),
sq AS (SELECT * FROM se WHERE scenario_code = 'status_quo'),
pp AS (SELECT * FROM se WHERE scenario_code = 'optimizer_profit'),
sv AS (SELECT * FROM se WHERE scenario_code = 'optimizer_service'),
i6 AS (SELECT * FROM se WHERE scenario_code = 'incentive_60'),
st AS (SELECT stress_case, (revenue_incentive - revenue_profit) / NULLIF(incentive_hours, 0) AS break_even
       FROM pbi.Stress_Cases),
checks AS (
    SELECT 1  AS n, 'Marketplace' AS area, 'Demand'                         AS check_measure, 'count' AS unit, CAST(mk.demand AS FLOAT) AS value FROM mk
    UNION ALL SELECT 2,  'Marketplace', 'Completed Jobs',                     'count', mk.completed FROM mk
    UNION ALL SELECT 3,  'Marketplace', 'Completion %',                       'pct',   100.0 * mk.completed / mk.demand FROM mk
    UNION ALL SELECT 4,  'Marketplace', 'Ride Completion %',                  'pct',   100.0 * mk.ride_completion FROM mk
    UNION ALL SELECT 5,  'Marketplace', 'Food Delivered %',                   'pct',   100.0 * mk.food_delivered FROM mk
    UNION ALL SELECT 6,  'Marketplace', 'Lost to No Partner %',               'pct',   100.0 * mk.lost / mk.demand FROM mk
    UNION ALL SELECT 7,  'Marketplace', 'Platform Revenue',                   'inr',   mk.revenue FROM mk
    UNION ALL SELECT 8,  'Marketplace', 'Revenue per Completed Job',          'inr',   mk.revenue / mk.completed FROM mk
    UNION ALL SELECT 9,  'Marketplace', 'Demand per Day',                     'count', mk.demand * 1.0 / dy.days FROM mk CROSS JOIN dy
    UNION ALL SELECT 10, 'Supply',      'Online Partner-Hours',               'count', sp.partner_hours FROM sp
    UNION ALL SELECT 11, 'Supply',      'Utilization %',                      'pct',   100.0 * sp.busy / sp.online FROM sp
    UNION ALL SELECT 12, 'Supply',      'Idle %',                             'pct',   100.0 * sp.idle / sp.online FROM sp
    UNION ALL SELECT 13, 'Supply',      'Empty km per Busy Hour',             'dec',   sp.empty_km / sp.busy FROM sp
    UNION ALL SELECT 14, 'Pressure',    'Under-supplied Zone-Hours %',        'pct',   100.0 * pr.under / pr.zone_hours FROM pr
    UNION ALL SELECT 15, 'Pressure',    'Reposition-Ahead Share of Lost %',   'pct',   100.0 * pr.lost_ahead / pr.lost FROM pr
    UNION ALL SELECT 16, 'Pressure',    'Citywide Share of Lost %',           'pct',   100.0 * pr.lost_city / pr.lost FROM pr
    UNION ALL SELECT 17, 'Forecast',    'WAPE % (GBM + rain)',                'pct',   100.0 * fc.wape_gbm FROM fc
    UNION ALL SELECT 18, 'Forecast',    'Skill vs Seasonal Naive % (GBM + rain)', 'pct', 100.0 * (1 - fc.wape_gbm / fc.wape_naive) FROM fc
    UNION ALL SELECT 19, 'Forecast',    'Flag Rate %',                        'pct',   100.0 * pf.flag_rate FROM pf
    UNION ALL SELECT 20, 'Forecast',    'Lost Jobs Captured %',               'pct',   100.0 * pf.captured FROM pf
    UNION ALL SELECT 21, 'Policy',      'Scenario Lost Jobs (status quo)',    'count', sq.lost_no_partner FROM sq
    UNION ALL SELECT 22, 'Policy',      'Lost Jobs Change vs SQ % (profit)',  'pct',   100.0 * (pp.lost_no_partner - sq.lost_no_partner) / sq.lost_no_partner FROM pp CROSS JOIN sq
    UNION ALL SELECT 23, 'Policy',      'Contribution Change vs SQ % (profit)', 'pct', 100.0 * (pp.contribution - sq.contribution) / sq.contribution FROM pp CROSS JOIN sq
    UNION ALL SELECT 24, 'Policy',      'Contribution Uplift per Day (profit)', 'inr', (pp.contribution - sq.contribution) / pp.days FROM pp CROSS JOIN sq
    UNION ALL SELECT 25, 'Policy',      'Moves per Day (profit)',             'dec',   pp.moves * 1.0 / pp.days FROM pp
    UNION ALL SELECT 26, 'Policy',      'Break-even Job Value (service vs profit)', 'inr',
                         (pp.contribution - sv.contribution) / NULLIF(sv.completed - pp.completed, 0) FROM pp CROSS JOIN sv
    UNION ALL SELECT 27, 'Incentives',  'Net vs Profit per Day (INR 60 bonus)', 'inr', (i6.contribution - pp.contribution) / i6.days FROM i6 CROSS JOIN pp
    UNION ALL SELECT 28, 'Incentives',  'Net Cost per Recovered Job (INR 60 bonus)', 'inr',
                         (pp.contribution - i6.contribution) / NULLIF(pp.lost_no_partner - i6.lost_no_partner, 0) FROM i6 CROSS JOIN pp
    UNION ALL SELECT 29, 'Incentives',  'Break-even Bonus (normal day)',      'inr',   break_even FROM st WHERE stress_case = 'normal'
    UNION ALL SELECT 30, 'Incentives',  'Break-even Bonus (festival evening)', 'inr',  break_even FROM st WHERE stress_case = 'festival_evening'
)
SELECT n                              AS [#],
       area                           AS [Area],
       check_measure                  AS [Check measure],
       unit                           AS [Unit],
       CAST(value AS DECIMAL(16,2))   AS [SQL value]
FROM checks
ORDER BY n;

/* ---- Result Set B ------------------------------------------------------- */
WITH se AS (SELECT * FROM pbi.Fact_Scenario_Economics),
sq AS (SELECT * FROM se WHERE scenario_code = 'status_quo'),
pp AS (SELECT * FROM se WHERE scenario_code = 'optimizer_profit')
SELECT d.scenario_short                                                                       AS [Scenario],
       se.completed                                                                           AS [Completed jobs],
       se.lost_no_partner                                                                     AS [Jobs lost to no partner],
       CAST(100.0 * (se.lost_no_partner - sq.lost_no_partner) / sq.lost_no_partner AS DECIMAL(6,1)) AS [Lost jobs vs status quo %],
       CAST(se.contribution AS DECIMAL(14,0))                                                 AS [Contribution (INR)],
       CAST((se.contribution - sq.contribution) / se.days AS DECIMAL(10,0))                   AS [Uplift per day vs status quo (INR)],
       CAST((se.contribution - pp.contribution) / se.days AS DECIMAL(10,0))                   AS [Net vs profit policy per day (INR)],
       CAST((se.completed - sq.completed) * 1.0 / se.days AS DECIMAL(8,0))                    AS [Extra completed jobs per day vs status quo]
FROM se
JOIN pbi.Dim_Scenario d ON d.scenario_code = se.scenario_code
CROSS JOIN sq
CROSS JOIN pp
ORDER BY d.scenario_sort;
