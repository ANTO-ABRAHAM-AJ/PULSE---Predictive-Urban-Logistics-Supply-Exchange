/* =========================================================================
   PULSE Data Warehouse - 03: indexes for analytics (run AFTER loading)
   Most queries slice facts by Zone x Time x Service, so index those keys.
   ========================================================================= */
USE PULSE_DW;
GO

CREATE INDEX IX_RideReq_Time_Zone   ON dw.Fact_Ride_Requests (time_key, pickup_zone_key) INCLUDE (request_status, is_completed);
CREATE INDEX IX_RideReq_Driver      ON dw.Fact_Ride_Requests (driver_key) WHERE driver_key IS NOT NULL;
CREATE INDEX IX_Rides_Time_Zone     ON dw.Fact_Rides (time_key, pickup_zone_key) INCLUDE (fare, platform_revenue, trip_km);
CREATE INDEX IX_Rides_Driver        ON dw.Fact_Rides (driver_key);
CREATE INDEX IX_Orders_Time_Zone    ON dw.Fact_Food_Orders (time_key, customer_zone_key) INCLUDE (order_status, is_delivered, order_value);
CREATE INDEX IX_Orders_Restaurant   ON dw.Fact_Food_Orders (restaurant_key);
CREATE INDEX IX_Orders_Driver       ON dw.Fact_Food_Orders (driver_key) WHERE driver_key IS NOT NULL;
CREATE INDEX IX_DelivEvents_Order   ON dw.Fact_Delivery_Events (order_key, event_seq);
CREATE INDEX IX_DelivEvents_Time    ON dw.Fact_Delivery_Events (time_key, event_type);
CREATE INDEX IX_Avail_Time_Zone     ON dw.Fact_Driver_Availability (time_key, zone_key) INCLUDE (online_minutes, busy_minutes, idle_minutes);
CREATE INDEX IX_Avail_Driver        ON dw.Fact_Driver_Availability (driver_key, time_key);
GO
