/* =========================================================================
   PULSE Phase 12 - 00: Power BI semantic layer (schema pbi)
   Every Power BI table is a view in schema pbi, so the report never reads
   dw tables directly and every column it needs is shaped here, once.

   Rules carried over from Phase 5 (KPI_Dictionary.md rule 4):
     * facts hold SUMS (numerators and denominators), never rates;
       every rate is a DAX measure SUM(numerator) / SUM(denominator)
     * one grain per fact, keys only, labels live in dimensions

   Import mode. Total rows across all views: about 1.2 million.
   Safe to re-run (CREATE OR ALTER).  Run after report_phase11.py.
   ========================================================================= */
USE PULSE_DW;
GO

IF SCHEMA_ID('pbi') IS NULL EXEC('CREATE SCHEMA pbi');
GO

/* ======================= DIMENSIONS ===================================== */

/* ---- Hour-level calendar (time_key = yyyymmddhh) ------------------------ */
CREATE OR ALTER VIEW pbi.Dim_Time AS
SELECT
    t.time_key,
    t.date_value,
    CAST(t.hour_of_day AS INT)                                              AS hour_of_day,
    RIGHT('0' + CAST(t.hour_of_day AS VARCHAR(2)), 2) + ':00'               AS hour_label,
    CAST(t.day_of_week AS INT)                                              AS day_of_week,
    t.day_name,
    LEFT(t.day_name, 3)                                                     AS day_short,
    CAST(t.week_number AS INT)                                              AS week_number,
    'W' + RIGHT('0' + CAST(t.week_number AS VARCHAR(2)), 2)                 AS week_label,
    CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END            AS day_type,
    CASE WHEN t.is_peak_hour = 1 THEN 'Weekday peak' ELSE 'Off-peak' END    AS peak_label,
    CASE WHEN t.is_rain_day = 1 THEN 'Rain day' ELSE 'Dry day' END          AS weather,
    CASE WHEN t.is_event_day = 1 THEN 'Event day' ELSE 'Normal day' END     AS event_flag,
    CASE WHEN t.hour_of_day BETWEEN 0 AND 5   THEN 'Night (00-05)'
         WHEN t.hour_of_day BETWEEN 6 AND 10  THEN 'Morning (06-10)'
         WHEN t.hour_of_day BETWEEN 11 AND 16 THEN 'Midday (11-16)'
         WHEN t.hour_of_day BETWEEN 17 AND 21 THEN 'Evening (17-21)'
         ELSE 'Late evening (22-23)' END                                    AS daypart,
    CASE WHEN t.hour_of_day BETWEEN 0 AND 5   THEN 1
         WHEN t.hour_of_day BETWEEN 6 AND 10  THEN 2
         WHEN t.hour_of_day BETWEEN 11 AND 16 THEN 3
         WHEN t.hour_of_day BETWEEN 17 AND 21 THEN 4
         ELSE 5 END                                                         AS daypart_sort,
    t.data_split,
    CASE WHEN t.data_split = 'spill'   THEN 'Spill day (after week 16)'
         WHEN t.week_number <= 8       THEN 'Weeks 1-8 History'
         WHEN t.week_number <= 12      THEN 'Weeks 9-12 Validation'
         ELSE 'Weeks 13-16 Holdout' END                                     AS period,
    CASE WHEN t.data_split = 'spill'   THEN 4
         WHEN t.week_number <= 8       THEN 1
         WHEN t.week_number <= 12      THEN 2
         ELSE 3 END                                                         AS period_sort
FROM dw.Dim_Time t;
GO

/* ---- Zone (also the Shape Map key: zone_code) --------------------------- */
CREATE OR ALTER VIEW pbi.Dim_Zone AS
SELECT
    z.zone_key,
    z.zone_code,
    z.zone_name,
    z.zone_code + ' - ' + z.zone_name                                       AS zone_label,
    CASE z.zone_type WHEN 'office'             THEN 'Office'
                     WHEN 'restaurant_cluster' THEN 'Restaurant cluster'
                     WHEN 'residential'        THEN 'Residential'
                     WHEN 'mixed'              THEN 'Mixed'
                     WHEN 'transit_hub'        THEN 'Transit hub'
                     ELSE z.zone_type END                                   AS zone_type,
    CASE z.zone_type WHEN 'office'             THEN 1
                     WHEN 'transit_hub'        THEN 2
                     WHEN 'restaurant_cluster' THEN 3
                     WHEN 'mixed'              THEN 4
                     ELSE 5 END                                             AS zone_type_sort,
    CAST(z.latitude  AS FLOAT)                                              AS latitude,
    CAST(z.longitude AS FLOAT)                                              AS longitude
FROM dw.Dim_Zone z;
GO

/* ---- Destination zone: role-playing copy for repositioning flows -------- */
CREATE OR ALTER VIEW pbi.Dim_Destination_Zone AS
SELECT zone_key   AS dest_zone_key,
       zone_code  AS dest_zone_code,
       zone_name  AS dest_zone_name,
       zone_label AS dest_zone_label,
       zone_type  AS dest_zone_type,
       latitude   AS dest_latitude,
       longitude  AS dest_longitude
FROM pbi.Dim_Zone;
GO

CREATE OR ALTER VIEW pbi.Dim_Service AS
SELECT CAST(service_key AS INT) AS service_key, service_code, service_name
FROM dw.Dim_Service;
GO

CREATE OR ALTER VIEW pbi.Dim_Vehicle AS
SELECT CAST(vehicle_key AS INT) AS vehicle_key, vehicle_code, vehicle_name
FROM dw.Dim_Vehicle;
GO

/* ---- Scenario: every simulated policy (Phases 10-11, holdout weeks) ----- */
CREATE OR ALTER VIEW pbi.Dim_Scenario AS
SELECT v.scenario_code, v.scenario_name, v.scenario_short, v.scenario_sort,
       v.lever, v.bonus, v.is_actionable, v.colour
FROM (VALUES
    ('status_quo',                 N'Status quo',                           N'Status quo',        1, 'Baseline',      0, 1, '#9AA4B2'),
    ('optimizer_profit',           N'Optimizer (profit)',                   N'Profit',            2, 'Repositioning', 0, 1, '#1B9E77'),
    ('optimizer_service',          N'Optimizer (service, ' + NCHAR(8377) + N'20 goodwill)',
                                                                            N'Service',           3, 'Repositioning', 0, 1, '#D95F02'),
    ('optimizer_perfect_forecast', N'Optimizer, perfect forecast',          N'Perfect forecast',  4, 'Benchmark',     0, 0, '#66A61E'),
    ('incentive_40',               N'Profit + ' + NCHAR(8377) + N'40 bonus', N'+' + NCHAR(8377) + N'40 bonus', 5, 'Incentive', 40, 1, '#7570B3'),
    ('incentive_60',               N'Profit + ' + NCHAR(8377) + N'60 bonus', N'+' + NCHAR(8377) + N'60 bonus', 6, 'Incentive', 60, 1, '#9E9AC8'),
    ('incentive_80',               N'Profit + ' + NCHAR(8377) + N'80 bonus', N'+' + NCHAR(8377) + N'80 bonus', 7, 'Incentive', 80, 1, '#CBC9E2')
) AS v (scenario_code, scenario_name, scenario_short, scenario_sort, lever, bonus, is_actionable, colour);
GO

/* ---- Forecast model (Phase 9) ------------------------------------------- */
CREATE OR ALTER VIEW pbi.Dim_Forecast_Model AS
SELECT v.model_name, v.model_sort, v.model_family, v.is_benchmark
FROM (VALUES
    ('Seasonal naive',  1, 'Benchmark',        1),
    ('4-week mean',     2, 'Simple smoother',  0),
    ('History profile', 3, 'Structural',       0),
    ('GBM calendar',    4, 'Machine learning', 0),
    ('GBM + rain',      5, 'Machine learning', 0)
) AS v (model_name, model_sort, model_family, is_benchmark);
GO

/* ======================= FACTS: OBSERVED MARKETPLACE (16 weeks) ========= */

/* ---- Demand and outcomes: zone x hour x service ------------------------- */
CREATE OR ALTER VIEW pbi.Fact_Marketplace AS
SELECT m.time_key, m.zone_key, 1 AS service_key,
       m.ride_requests                      AS demand,
       m.completed_rides                    AS completed,
       m.cancelled_no_partner               AS lost_no_partner,
       m.cancelled_customer                 AS cancelled_customer,
       0                                    AS cancelled_other,
       CAST(m.pickup_eta_min_sum AS FLOAT)  AS wait_min_sum,        -- rides: pickup ETA
       CAST(m.gross_booking_value AS FLOAT) AS gross_value,
       CAST(m.partner_payout AS FLOAT)      AS partner_payout,
       CAST(m.platform_revenue AS FLOAT)    AS platform_revenue
FROM dw.vw_Mobility_ZoneHour m
UNION ALL
SELECT f.time_key, f.zone_key, 2,
       f.food_orders,
       f.delivered_orders,
       f.cancelled_no_partner,
       f.cancelled_customer,
       f.cancelled_restaurant,
       CAST(f.order_to_door_min_sum AS FLOAT),                       -- food: order to door
       CAST(f.gmv AS FLOAT),
       CAST(f.partner_payout AS FLOAT),
       CAST(f.platform_revenue AS FLOAT)
FROM dw.vw_Food_ZoneHour f;
GO

/* ---- Supply: zone x hour x vehicle -------------------------------------- */
CREATE OR ALTER VIEW pbi.Fact_Supply AS
SELECT s.time_key, s.zone_key, CAST(s.vehicle_key AS INT) AS vehicle_key,
       s.partner_hours,
       CAST(s.online_hours AS FLOAT) AS online_hours,
       CAST(s.busy_hours   AS FLOAT) AS busy_hours,
       CAST(s.idle_hours   AS FLOAT) AS idle_hours,
       CAST(s.empty_km     AS FLOAT) AS empty_km
FROM dw.vw_Supply_ZoneHour s;
GO

/* ---- Pressure: zone x hour (Phase 8 MPI) -------------------------------- */
CREATE OR ALTER VIEW pbi.Fact_Pressure AS
SELECT p.time_key, p.zone_key,
       p.ride_requests, p.food_orders,
       p.ride_requests + p.food_orders                AS demand_jobs,
       p.lost_rides, p.lost_orders,
       p.lost_rides + p.lost_orders                   AS lost_jobs,
       CAST(p.work_hours        AS FLOAT)             AS work_hours,
       p.supply_hours,
       p.two_wheeler_hours,
       CAST(p.nbhd_work_hours   AS FLOAT)             AS nbhd_work_hours,
       p.nbhd_supply_hours,
       CAST(p.local_mpi AS FLOAT)                     AS local_mpi,       -- for row-level bins only
       p.pressure_state,
       CASE p.pressure_state WHEN 'Under-supplied' THEN 1 WHEN 'Balanced' THEN 2
                             WHEN 'Over-supplied'  THEN 3 ELSE 4 END        AS pressure_state_sort,
       p.shortage_type,
       CASE p.shortage_type WHEN 'Reposition ahead'  THEN 1 WHEN 'Citywide shortage' THEN 2
                            WHEN 'Fix now'           THEN 3 ELSE 4 END      AS shortage_type_sort,
       CASE p.shortage_type WHEN 'Reposition ahead'  THEN 'Move supply before demand (Phase 10)'
                            WHEN 'Citywide shortage' THEN 'Bring more partners online (Phase 11)'
                            WHEN 'Fix now'           THEN 'Better same-hour dispatch'
                            ELSE 'No shortage' END                          AS lever,
       CASE WHEN p.pressure_state = 'Under-supplied' THEN 1 ELSE 0 END      AS is_under_supplied
FROM dw.Agg_Pressure_ZoneHour p;
GO

/* ======================= FACTS: FORECASTS (holdout weeks) =============== */

CREATE OR ALTER VIEW pbi.Fact_Demand_Forecast AS
SELECT f.time_key, f.zone_key, CAST(f.service_key AS INT) AS service_key, f.model_name,
       CAST(f.forecast_demand AS FLOAT)                         AS forecast_demand,
       f.actual_demand,
       CAST(ABS(f.forecast_demand - f.actual_demand) AS FLOAT)  AS abs_error   -- WAPE numerator at stored grain
FROM dw.Fact_Demand_Forecast f;
GO

CREATE OR ALTER VIEW pbi.Fact_Pressure_Forecast AS
SELECT f.time_key, f.zone_key,
       CAST(f.forecast_work_hours   AS FLOAT) AS forecast_work_hours,
       CAST(f.forecast_supply_hours AS FLOAT) AS forecast_supply_hours,
       CAST(f.forecast_mpi          AS FLOAT) AS forecast_mpi,
       CAST(f.predicted_short AS INT)         AS predicted_short,
       CAST(f.actual_short    AS INT)         AS actual_short,
       f.lost_jobs,
       CASE WHEN f.predicted_short = 1 AND f.actual_short = 1 THEN 'Correct warning'
            WHEN f.predicted_short = 1                        THEN 'False alarm'
            WHEN f.actual_short = 1                           THEN 'Missed shortage'
            ELSE 'Correct all-clear' END                          AS outcome,
       CASE WHEN f.predicted_short = 1 AND f.actual_short = 1 THEN 1
            WHEN f.predicted_short = 1                        THEN 2
            WHEN f.actual_short = 1                           THEN 3
            ELSE 4 END                                            AS outcome_sort
FROM dw.Fact_Pressure_Forecast f;
GO

/* ======================= FACTS: SIMULATED POLICIES (holdout weeks) ====== */

/* ---- Outcome per scenario x zone x hour x service ----------------------- */
CREATE OR ALTER VIEW pbi.Fact_Policy AS
SELECT p.scenario_code, p.time_key, p.zone_key, CAST(p.service_key AS INT) AS service_key,
       p.requests, p.completed, p.lost_no_partner, p.cancelled_customer,
       CAST(p.revenue AS FLOAT) AS revenue
FROM dw.Agg_Policy_ZoneHour p;
GO

/* ---- Repositioning moves, aggregated to scenario x hour x corridor ------ */
CREATE OR ALTER VIEW pbi.Fact_Repositioning AS
SELECT r.scenario_code, r.time_key, r.origin_zone_key, r.dest_zone_key,
       COUNT(*)                                    AS moves,
       CAST(SUM(r.reposition_km)      AS FLOAT)    AS reposition_km,
       CAST(SUM(r.reposition_minutes) AS FLOAT)    AS reposition_minutes,
       CAST(SUM(r.reposition_cost)    AS FLOAT)    AS reposition_cost
FROM dw.Fact_Repositioning r
GROUP BY r.scenario_code, r.time_key, r.origin_zone_key, r.dest_zone_key;
GO

/* ---- Value of one more partner (LP shadow price) ------------------------ */
CREATE OR ALTER VIEW pbi.Fact_Supply_Value AS
SELECT v.scenario_code, v.time_key, v.zone_key, CAST(v.vehicle_key AS INT) AS vehicle_key,
       CAST(v.shadow_price AS FLOAT) AS shadow_price
FROM dw.Agg_Supply_Value v;
GO

/* ---- Incentive programmes: scenario x hour x zone ----------------------- */
CREATE OR ALTER VIEW pbi.Fact_Incentives AS
SELECT i.scenario_code, i.time_key, i.zone_key,
       CAST(SUM(i.extra_partner_hours) AS FLOAT) AS incentive_partner_hours,
       CAST(SUM(i.incentive_amount)    AS FLOAT) AS incentive_cost
FROM dw.Fact_Incentives i
GROUP BY i.scenario_code, i.time_key, i.zone_key;
GO

/* ---- Scenario economics: one row per scenario (whole holdout) ----------- */
/* Phase 10 scenarios: revenue from Agg_Policy_ZoneHour, cost from moves.    */
/* Phase 11 incentive scenarios: repositioning and incentive cost from       */
/* Agg_Scenario_Summary (their individual moves are not stored).             */
CREATE OR ALTER VIEW pbi.Fact_Scenario_Economics AS
WITH pol AS (
    SELECT scenario_code,
           SUM(requests) AS requests, SUM(completed) AS completed,
           SUM(lost_no_partner) AS lost_no_partner, SUM(cancelled_customer) AS cancelled_customer,
           SUM(revenue) AS revenue
    FROM dw.Agg_Policy_ZoneHour
    GROUP BY scenario_code
),
mv AS (
    SELECT scenario_code, COUNT(*) AS moves, SUM(reposition_km) AS km, SUM(reposition_cost) AS cost
    FROM dw.Fact_Repositioning
    GROUP BY scenario_code
),
inc AS (
    SELECT scenario_code, reposition_cost, incentive_cost, incentive_partner_hours
    FROM dw.Agg_Scenario_Summary
    WHERE study = 'incentive'
),
d AS (
    SELECT COUNT(DISTINCT date_value) AS days,
           COUNT(DISTINCT CASE WHEN is_weekend = 0 THEN date_value END) AS weekdays
    FROM dw.Dim_Time
    WHERE data_split = 'holdout'
)
SELECT p.scenario_code,
       d.days,
       d.weekdays,
       p.requests,
       p.completed,
       p.lost_no_partner,
       p.cancelled_customer,
       CAST(p.revenue AS FLOAT)                                              AS revenue,
       mv.moves,                                                             -- NULL: not stored
       CAST(COALESCE(mv.km, 0) AS FLOAT)                                     AS reposition_km,
       CAST(COALESCE(mv.cost, i.reposition_cost, 0) AS FLOAT)                AS reposition_cost,
       CAST(ISNULL(i.incentive_cost, 0) AS FLOAT)                            AS incentive_cost,
       ISNULL(i.incentive_partner_hours, 0)                                  AS incentive_partner_hours_per_weekday,
       CAST(p.revenue - COALESCE(mv.cost, i.reposition_cost, 0)
                      - ISNULL(i.incentive_cost, 0) AS FLOAT)                AS contribution
FROM pol p
CROSS JOIN d
LEFT JOIN mv  ON mv.scenario_code = p.scenario_code
LEFT JOIN inc i ON i.scenario_code = p.scenario_code;
GO

/* ======================= STRESS TESTS (Phase 11, 14 holdout days) ======= */

/* ---- Long: one row per stress case x policy ----------------------------- */
CREATE OR ALTER VIEW pbi.Stress_Summary AS
SELECT s.scenario_code,
       s.stress_case,
       CASE s.stress_case WHEN 'normal'           THEN 'Normal day'
                          WHEN 'rain_every_day'   THEN 'Rain every day'
                          WHEN 'festival_evening' THEN 'Festival evening'
                          WHEN 'partner_shortage' THEN 'Partner shortage'
                          WHEN 'demand_surge'     THEN 'Demand surge'
                          ELSE s.stress_case END                                 AS stress_label,
       CASE s.stress_case WHEN 'normal' THEN 1 WHEN 'demand_surge' THEN 2
                          WHEN 'rain_every_day' THEN 3 WHEN 'partner_shortage' THEN 4
                          WHEN 'festival_evening' THEN 5 ELSE 6 END              AS stress_sort,
       s.policy,
       CASE s.policy WHEN 'status_quo' THEN 'Status quo' WHEN 'profit' THEN 'Profit'
                     WHEN 'service' THEN 'Service' ELSE 'Profit + incentive' END AS policy_label,
       CASE s.policy WHEN 'status_quo' THEN 1 WHEN 'profit' THEN 2
                     WHEN 'service' THEN 3 ELSE 4 END                            AS policy_sort,
       CAST(s.bonus AS FLOAT)                                                    AS bonus,
       s.days, s.requests, s.completed, s.lost_no_partner,
       CAST(s.revenue         AS FLOAT)                                          AS revenue,
       CAST(s.reposition_cost AS FLOAT)                                          AS reposition_cost,
       CAST(s.incentive_cost  AS FLOAT)                                          AS incentive_cost,
       CAST(CASE WHEN s.bonus > 0 THEN s.incentive_cost / s.bonus ELSE 0 END AS FLOAT) AS incentive_hours,
       CAST(s.contribution    AS FLOAT)                                          AS contribution
FROM dw.Agg_Scenario_Summary s
WHERE s.study = 'stress';
GO

/* ---- Wide: one row per stress case (drives the bonus what-if slider) ---- */
CREATE OR ALTER VIEW pbi.Stress_Cases AS
SELECT stress_case, stress_label, stress_sort,
       MAX(days)                                                                  AS days,
       MAX(CASE WHEN policy = 'status_quo'         THEN lost_no_partner END)      AS lost_status_quo,
       MAX(CASE WHEN policy = 'profit'             THEN lost_no_partner END)      AS lost_profit,
       MAX(CASE WHEN policy = 'service'            THEN lost_no_partner END)      AS lost_service,
       MAX(CASE WHEN policy = 'profit + incentive' THEN lost_no_partner END)      AS lost_incentive,
       MAX(CASE WHEN policy = 'profit'             THEN revenue END)              AS revenue_profit,
       MAX(CASE WHEN policy = 'profit + incentive' THEN revenue END)              AS revenue_incentive,
       MAX(CASE WHEN policy = 'profit + incentive' THEN incentive_hours END)      AS incentive_hours,
       MAX(CASE WHEN policy = 'profit + incentive' THEN bonus END)                AS simulated_bonus
FROM pbi.Stress_Summary
GROUP BY stress_case, stress_label, stress_sort;
GO
