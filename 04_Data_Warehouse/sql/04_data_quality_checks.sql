/* =========================================================================
   PULSE Data Warehouse - 04: data-quality checks
   Every row reports how many records FAIL a rule. All should be 0.
   (Row counts vs source files are checked by the Python loader.)
   ========================================================================= */
USE PULSE_DW;

SELECT check_name, failing_rows FROM (
    SELECT 'Completed requests without a ride row' AS check_name,
           COUNT(*) AS failing_rows
    FROM dw.Fact_Ride_Requests r
    LEFT JOIN dw.Fact_Rides f ON f.ride_request_key = r.ride_request_key
    WHERE r.is_completed = 1 AND f.ride_key IS NULL
UNION ALL
    SELECT 'Completed requests without a driver', COUNT(*)
    FROM dw.Fact_Ride_Requests WHERE is_completed = 1 AND driver_key IS NULL
UNION ALL
    SELECT 'No-partner cancellations that have a driver', COUNT(*)
    FROM dw.Fact_Ride_Requests WHERE request_status = 'cancelled_no_partner' AND driver_key IS NOT NULL
UNION ALL
    SELECT 'Rides ending before they start', COUNT(*)
    FROM dw.Fact_Rides WHERE dropoff_ts <= pickup_ts
UNION ALL
    SELECT 'Rides with payout >= fare', COUNT(*)
    FROM dw.Fact_Rides WHERE partner_payout >= fare
UNION ALL
    SELECT 'Delivered orders missing a timestamp', COUNT(*)
    FROM dw.Fact_Food_Orders
    WHERE is_delivered = 1 AND (assigned_ts IS NULL OR ready_ts IS NULL OR picked_ts IS NULL OR delivered_ts IS NULL)
UNION ALL
    SELECT 'Orders with timestamps out of order', COUNT(*)
    FROM dw.Fact_Food_Orders
    WHERE is_delivered = 1 AND (ready_ts < placed_ts OR picked_ts < ready_ts OR delivered_ts <= picked_ts)
UNION ALL
    SELECT 'Delivered orders delivered by a four-wheeler', COUNT(*)
    FROM dw.Fact_Food_Orders o JOIN dw.Dim_Driver d ON d.driver_key = o.driver_key
    JOIN dw.Dim_Vehicle v ON v.vehicle_key = d.vehicle_key
    WHERE v.can_food = 0
UNION ALL
    SELECT 'Orders without a "placed" event', COUNT(*)
    FROM dw.Fact_Food_Orders o
    WHERE NOT EXISTS (SELECT 1 FROM dw.Fact_Delivery_Events e
                      WHERE e.order_key = o.order_key AND e.event_type = 'placed')
UNION ALL
    SELECT 'Partner-hours with busy > online', COUNT(*)
    FROM dw.Fact_Driver_Availability WHERE busy_minutes > online_minutes
UNION ALL
    SELECT 'Partner-hours with negative idle time', COUNT(*)
    FROM dw.Fact_Driver_Availability WHERE idle_minutes < 0
UNION ALL
    SELECT 'Negative money values', COUNT(*)
    FROM dw.Fact_Food_Orders WHERE order_value < 0 OR partner_payout < 0
) checks
ORDER BY check_name;
