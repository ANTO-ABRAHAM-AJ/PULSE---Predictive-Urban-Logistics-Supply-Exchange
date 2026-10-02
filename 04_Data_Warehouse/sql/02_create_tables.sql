/* =========================================================================
   PULSE Data Warehouse - 02: star schema (drops and recreates all tables)
   Run against: PULSE_DW.  Re-running deletes all warehouse data.

   Grain conventions
     * time_key  = yyyymmddhh (INT) of the hour the event STARTED
     * money     = INR, DECIMAL(12,2)
     * distances = km, DECIMAL(9,2); durations = minutes, DECIMAL(9,2)
     * timestamps = DATETIME2(0), local Bengaluru time
   ========================================================================= */
USE PULSE_DW;
GO

/* ---- drop facts first (they reference dimensions) ---------------------- */
DROP TABLE IF EXISTS dw.Fact_Delivery_Events;
DROP TABLE IF EXISTS dw.Fact_Rides;
DROP TABLE IF EXISTS dw.Fact_Ride_Requests;
DROP TABLE IF EXISTS dw.Fact_Food_Orders;
DROP TABLE IF EXISTS dw.Fact_Driver_Availability;
DROP TABLE IF EXISTS dw.Fact_Incentives;
DROP TABLE IF EXISTS dw.Fact_Supply_Allocation;
DROP TABLE IF EXISTS dw.Fact_Repositioning;
DROP TABLE IF EXISTS dw.Dim_Driver;
DROP TABLE IF EXISTS dw.Dim_Customer;
DROP TABLE IF EXISTS dw.Dim_Restaurant;
DROP TABLE IF EXISTS dw.Dim_Time;
DROP TABLE IF EXISTS dw.Dim_Zone;
DROP TABLE IF EXISTS dw.Dim_Service;
DROP TABLE IF EXISTS dw.Dim_Vehicle;
GO

/* ======================= DIMENSIONS ===================================== */
CREATE TABLE dw.Dim_Time (
    time_key        INT          NOT NULL PRIMARY KEY,   -- yyyymmddhh
    date_value      DATE         NOT NULL,
    hour_of_day     TINYINT      NOT NULL,
    day_of_week     TINYINT      NOT NULL,                -- 1 = Monday
    day_name        VARCHAR(9)   NOT NULL,
    week_number     TINYINT      NOT NULL,                -- 1 = first simulated week
    is_weekend      BIT          NOT NULL,
    is_peak_hour    BIT          NOT NULL,                -- weekday traffic peak (C-05)
    is_rain_day     BIT          NOT NULL,
    is_event_day    BIT          NOT NULL,
    data_split      VARCHAR(7)   NOT NULL                 -- history / holdout
);

CREATE TABLE dw.Dim_Zone (
    zone_key        SMALLINT     NOT NULL PRIMARY KEY,
    zone_code       CHAR(3)      NOT NULL UNIQUE,
    zone_name       VARCHAR(40)  NOT NULL,
    zone_type       VARCHAR(20)  NOT NULL,
    latitude        DECIMAL(9,6) NOT NULL,
    longitude       DECIMAL(9,6) NOT NULL,
    city            VARCHAR(20)  NOT NULL
);

CREATE TABLE dw.Dim_Service (
    service_key     TINYINT      NOT NULL PRIMARY KEY,
    service_code    VARCHAR(10)  NOT NULL UNIQUE,
    service_name    VARCHAR(20)  NOT NULL
);

CREATE TABLE dw.Dim_Vehicle (
    vehicle_key     TINYINT      NOT NULL PRIMARY KEY,
    vehicle_code    VARCHAR(15)  NOT NULL UNIQUE,
    vehicle_name    VARCHAR(20)  NOT NULL,
    can_mobility    BIT          NOT NULL,
    can_food        BIT          NOT NULL
);

CREATE TABLE dw.Dim_Driver (
    driver_key      INT          NOT NULL PRIMARY KEY,
    partner_code    VARCHAR(8)   NOT NULL UNIQUE,
    vehicle_key     TINYINT      NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    home_zone_key   SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    shift_type      VARCHAR(10)  NOT NULL
);

CREATE TABLE dw.Dim_Customer (
    customer_key    INT          NOT NULL PRIMARY KEY,
    customer_code   VARCHAR(8)   NOT NULL UNIQUE,
    home_zone_key   SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key)
);

CREATE TABLE dw.Dim_Restaurant (
    restaurant_key  INT          NOT NULL PRIMARY KEY,
    restaurant_code VARCHAR(10)  NOT NULL UNIQUE,
    zone_key        SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    cuisine         VARCHAR(20)  NOT NULL
);
GO

/* ======================= MOBILITY FACTS ================================= */
CREATE TABLE dw.Fact_Ride_Requests (            -- every request, incl. cancelled
    ride_request_key INT          NOT NULL PRIMARY KEY,
    request_code     VARCHAR(10)  NOT NULL UNIQUE,
    time_key         INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    customer_key     INT          NOT NULL REFERENCES dw.Dim_Customer(customer_key),
    pickup_zone_key  SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    dropoff_zone_key SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    driver_key       INT          NULL     REFERENCES dw.Dim_Driver(driver_key),
    vehicle_key      TINYINT      NULL     REFERENCES dw.Dim_Vehicle(vehicle_key),
    request_ts       DATETIME2(0) NOT NULL,
    assigned_ts      DATETIME2(0) NULL,
    request_status   VARCHAR(25)  NOT NULL,    -- completed / cancelled_customer / cancelled_no_partner
    is_completed     BIT          NOT NULL,
    requested_trip_km DECIMAL(9,2) NOT NULL,
    pickup_km        DECIMAL(9,2) NULL,
    pickup_eta_min   DECIMAL(9,2) NULL
);

CREATE TABLE dw.Fact_Rides (                    -- completed trips only
    ride_key         INT          NOT NULL PRIMARY KEY,
    ride_request_key INT          NOT NULL REFERENCES dw.Fact_Ride_Requests(ride_request_key),
    time_key         INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    customer_key     INT          NOT NULL REFERENCES dw.Dim_Customer(customer_key),
    driver_key       INT          NOT NULL REFERENCES dw.Dim_Driver(driver_key),
    vehicle_key      TINYINT      NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    pickup_zone_key  SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    dropoff_zone_key SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    pickup_ts        DATETIME2(0) NOT NULL,
    dropoff_ts       DATETIME2(0) NOT NULL,
    trip_km          DECIMAL(9,2) NOT NULL,
    trip_minutes     DECIMAL(9,2) NOT NULL,
    pickup_km        DECIMAL(9,2) NOT NULL,
    fare             DECIMAL(12,2) NOT NULL,
    partner_payout   DECIMAL(12,2) NOT NULL,
    platform_revenue DECIMAL(12,2) NOT NULL,   -- fare - partner_payout
    CONSTRAINT UQ_Rides_Request UNIQUE (ride_request_key)   -- one ride per request
);
GO

/* ======================= FOOD FACTS ===================================== */
CREATE TABLE dw.Fact_Food_Orders (              -- every order, incl. cancelled
    order_key           INT          NOT NULL PRIMARY KEY,
    order_code          VARCHAR(10)  NOT NULL UNIQUE,
    time_key            INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    customer_key        INT          NOT NULL REFERENCES dw.Dim_Customer(customer_key),
    customer_zone_key   SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    restaurant_key      INT          NOT NULL REFERENCES dw.Dim_Restaurant(restaurant_key),
    restaurant_zone_key SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    driver_key          INT          NULL     REFERENCES dw.Dim_Driver(driver_key),
    placed_ts           DATETIME2(0) NOT NULL,
    assigned_ts         DATETIME2(0) NULL,
    ready_ts            DATETIME2(0) NULL,
    picked_ts           DATETIME2(0) NULL,
    delivered_ts        DATETIME2(0) NULL,
    order_status        VARCHAR(25)  NOT NULL,  -- delivered / cancelled_customer / cancelled_no_partner / cancelled_restaurant
    is_delivered        BIT          NOT NULL,
    order_value         DECIMAL(12,2) NOT NULL,
    commission          DECIMAL(12,2) NULL,
    delivery_fee        DECIMAL(12,2) NULL,
    partner_payout      DECIMAL(12,2) NULL,
    platform_revenue    DECIMAL(12,2) NULL,     -- commission + delivery_fee - partner_payout
    pickup_km           DECIMAL(9,2) NULL,
    delivery_km         DECIMAL(9,2) NULL,
    prep_minutes        DECIMAL(9,2) NULL,      -- placed -> ready
    delivery_minutes    DECIMAL(9,2) NULL       -- placed -> delivered
);

CREATE TABLE dw.Fact_Delivery_Events (          -- one row per order milestone
    delivery_event_key BIGINT       NOT NULL PRIMARY KEY,
    order_key          INT          NOT NULL REFERENCES dw.Fact_Food_Orders(order_key),
    event_type         VARCHAR(12)  NOT NULL,  -- placed / assigned / food_ready / picked_up / delivered / cancelled
    event_seq          TINYINT      NOT NULL,
    event_ts           DATETIME2(0) NOT NULL,
    time_key           INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key           SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    driver_key         INT          NULL     REFERENCES dw.Dim_Driver(driver_key)
);
GO

/* ======================= SUPPLY FACTS =================================== */
CREATE TABLE dw.Fact_Driver_Availability (      -- partner x online hour
    availability_key BIGINT       NOT NULL PRIMARY KEY,
    time_key         INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    driver_key       INT          NOT NULL REFERENCES dw.Dim_Driver(driver_key),
    zone_key         SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),  -- location at hour start
    vehicle_key      TINYINT      NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    online_minutes   DECIMAL(5,2) NOT NULL,
    busy_minutes     DECIMAL(5,2) NOT NULL,
    idle_minutes     DECIMAL(5,2) NOT NULL,
    empty_km         DECIMAL(9,2) NOT NULL
);

/* ---- filled by Phases 10-11 (empty in status-quo history) -------------- */
CREATE TABLE dw.Fact_Supply_Allocation (        -- optimizer output
    allocation_key    BIGINT        NOT NULL PRIMARY KEY,
    scenario_code     VARCHAR(40)   NOT NULL,
    run_ts            DATETIME2(0)  NOT NULL,
    time_key          INT           NOT NULL REFERENCES dw.Dim_Time(time_key),
    origin_zone_key   SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    dest_zone_key     SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    vehicle_key       TINYINT       NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    service_key       TINYINT       NOT NULL REFERENCES dw.Dim_Service(service_key),
    partners          DECIMAL(9,2)  NOT NULL,
    reposition_cost   DECIMAL(12,2) NOT NULL
);

CREATE TABLE dw.Fact_Repositioning (            -- individual moves in simulation
    repositioning_key BIGINT        NOT NULL PRIMARY KEY,
    scenario_code     VARCHAR(40)   NOT NULL,
    time_key          INT           NOT NULL REFERENCES dw.Dim_Time(time_key),
    driver_key        INT           NOT NULL REFERENCES dw.Dim_Driver(driver_key),
    origin_zone_key   SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    dest_zone_key     SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    reposition_km     DECIMAL(9,2)  NOT NULL,
    reposition_minutes DECIMAL(9,2) NOT NULL,
    reposition_cost   DECIMAL(12,2) NOT NULL
);

CREATE TABLE dw.Fact_Incentives (
    incentive_key       BIGINT        NOT NULL PRIMARY KEY,
    scenario_code       VARCHAR(40)   NOT NULL,
    time_key            INT           NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key            SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    service_key         TINYINT       NOT NULL REFERENCES dw.Dim_Service(service_key),
    driver_key          INT           NULL     REFERENCES dw.Dim_Driver(driver_key),
    incentive_type      VARCHAR(20)   NOT NULL,
    incentive_amount    DECIMAL(12,2) NOT NULL,
    extra_partner_hours DECIMAL(9,2)  NULL
);
GO
