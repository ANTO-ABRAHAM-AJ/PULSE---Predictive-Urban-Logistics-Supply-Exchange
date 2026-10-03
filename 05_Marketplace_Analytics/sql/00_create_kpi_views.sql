/* =========================================================================
   PULSE Phase 5 - 00: KPI views (single source of truth for every KPI)
   Grain: Zone x Hour (time_key) [x Service / Vehicle].
   Views hold SUMS (numerators and denominators), never pre-computed rates,
   so any aggregation (zone type, hour, week, city) can compute rates
   correctly as SUM(numerator) / SUM(denominator).  KPI_Dictionary.md rule 4.
   Safe to re-run (CREATE OR ALTER).
   ========================================================================= */
USE PULSE_DW;
GO

/* ---- Mobility: one row per pickup zone x hour --------------------------- */
CREATE OR ALTER VIEW dw.vw_Mobility_ZoneHour AS
SELECT
    r.time_key,
    r.pickup_zone_key                                                        AS zone_key,
    COUNT(*)                                                                 AS ride_requests,
    SUM(CASE WHEN r.request_status = 'completed'            THEN 1 ELSE 0 END) AS completed_rides,
    SUM(CASE WHEN r.request_status = 'cancelled_customer'   THEN 1 ELSE 0 END) AS cancelled_customer,
    SUM(CASE WHEN r.request_status = 'cancelled_no_partner' THEN 1 ELSE 0 END) AS cancelled_no_partner,
    SUM(CASE WHEN r.request_status = 'completed' THEN r.pickup_eta_min ELSE 0 END) AS pickup_eta_min_sum,
    ISNULL(SUM(f.trip_km), 0)                                                AS trip_km_sum,
    ISNULL(SUM(f.fare), 0)                                                   AS gross_booking_value,
    ISNULL(SUM(f.partner_payout), 0)                                         AS partner_payout,
    ISNULL(SUM(f.platform_revenue), 0)                                       AS platform_revenue
FROM dw.Fact_Ride_Requests r
LEFT JOIN dw.Fact_Rides f ON f.ride_request_key = r.ride_request_key
GROUP BY r.time_key, r.pickup_zone_key;
GO

/* ---- Food: one row per customer zone x hour ----------------------------- */
CREATE OR ALTER VIEW dw.vw_Food_ZoneHour AS
SELECT
    o.time_key,
    o.customer_zone_key                                                      AS zone_key,
    COUNT(*)                                                                 AS food_orders,
    SUM(CASE WHEN o.order_status = 'delivered'            THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN o.order_status = 'cancelled_customer'   THEN 1 ELSE 0 END) AS cancelled_customer,
    SUM(CASE WHEN o.order_status = 'cancelled_no_partner' THEN 1 ELSE 0 END) AS cancelled_no_partner,
    SUM(CASE WHEN o.order_status = 'cancelled_restaurant' THEN 1 ELSE 0 END) AS cancelled_restaurant,
    SUM(CASE WHEN o.is_delivered = 1 THEN o.prep_minutes     ELSE 0 END)     AS prep_min_sum,
    SUM(CASE WHEN o.is_delivered = 1 THEN o.delivery_minutes ELSE 0 END)     AS order_to_door_min_sum,
    SUM(CASE WHEN o.is_delivered = 1 THEN o.order_value      ELSE 0 END)     AS gmv,
    ISNULL(SUM(o.commission), 0)                                             AS commission,
    ISNULL(SUM(o.delivery_fee), 0)                                           AS delivery_fee,
    ISNULL(SUM(o.partner_payout), 0)                                         AS partner_payout,
    ISNULL(SUM(o.platform_revenue), 0)                                       AS platform_revenue
FROM dw.Fact_Food_Orders o
GROUP BY o.time_key, o.customer_zone_key;
GO

/* ---- Supply: one row per zone x hour x vehicle -------------------------- */
CREATE OR ALTER VIEW dw.vw_Supply_ZoneHour AS
SELECT
    a.time_key,
    a.zone_key,
    a.vehicle_key,
    COUNT(*)                         AS partner_hours,      -- one row = one online partner-hour
    SUM(a.online_minutes) / 60.0     AS online_hours,
    SUM(a.busy_minutes)   / 60.0     AS busy_hours,
    SUM(a.idle_minutes)   / 60.0     AS idle_hours,
    SUM(a.empty_km)                  AS empty_km
FROM dw.Fact_Driver_Availability a
GROUP BY a.time_key, a.zone_key, a.vehicle_key;
GO

/* ---- Marketplace: both services side by side ---------------------------- */
CREATE OR ALTER VIEW dw.vw_Marketplace_ZoneHour AS
SELECT time_key, zone_key, CAST(1 AS TINYINT) AS service_key,
       ride_requests        AS demand,
       completed_rides      AS completed,
       cancelled_no_partner AS lost_no_partner,
       gross_booking_value  AS gross_value,
       partner_payout,
       platform_revenue
FROM dw.vw_Mobility_ZoneHour
UNION ALL
SELECT time_key, zone_key, CAST(2 AS TINYINT),
       food_orders, delivered_orders, cancelled_no_partner,
       gmv, partner_payout, platform_revenue
FROM dw.vw_Food_ZoneHour;
GO
