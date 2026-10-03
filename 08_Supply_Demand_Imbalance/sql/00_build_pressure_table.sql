/* =========================================================================
   PULSE Phase 8 - 00: build dw.Agg_Pressure_ZoneHour
   The Marketplace Pressure Index (MPI) for every Zone x Hour (and Service),
   stored as a table because Phase 10 optimization reads it as an input.
   Safe to re-run (drops and rebuilds).

   Definitions (KPI_Dictionary.md section 4, Assumption O-01):
     work hours      = rides / 2 + food orders / 3   (partner-hours requested)
     supply hours    = partners present at the start of the hour
     local MPI       = work hours / supply hours in the zone
     neighbourhood   = zones reachable in 20 minutes (5 km weekday peak,
                       8.3 km otherwise; road km = straight km x 1.4)
     city MPI        = all work / all supply in that hour
     mobility MPI    = rides  / (2 x all partners present)
     food MPI        = orders / (3 x two-wheelers present)
   States: Under-supplied (MPI > 1.10, or demand with no supply),
           Balanced (0.80 - 1.10), Over-supplied (< 0.80), No activity.
   Shortage type (Under-supplied zone-hours only):
     Fix now            - neighbourhood MPI <= 1.10 (slack within reach now)
     Reposition ahead   - neighbourhood short, city MPI <= 1.10 (slack elsewhere)
     Citywide shortage  - city MPI > 1.10 (not enough partners online)
   ========================================================================= */
USE PULSE_DW;
GO

DROP TABLE IF EXISTS dw.Agg_Pressure_ZoneHour;
GO

CREATE TABLE dw.Agg_Pressure_ZoneHour (
    time_key            INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key            SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    ride_requests       INT          NOT NULL,
    food_orders         INT          NOT NULL,
    lost_rides          INT          NOT NULL,
    lost_orders         INT          NOT NULL,
    work_hours          DECIMAL(9,3) NOT NULL,
    supply_hours        INT          NOT NULL,
    two_wheeler_hours   INT          NOT NULL,
    local_mpi           DECIMAL(9,3) NULL,      -- NULL when no supply
    nbhd_work_hours     DECIMAL(10,3) NOT NULL,
    nbhd_supply_hours   INT          NOT NULL,
    nbhd_mpi            DECIMAL(9,3) NULL,
    city_mpi            DECIMAL(9,3) NULL,
    mobility_mpi        DECIMAL(9,3) NULL,
    food_mpi            DECIMAL(9,3) NULL,
    pressure_state      VARCHAR(15)  NOT NULL,
    shortage_type       VARCHAR(20)  NOT NULL,
    CONSTRAINT PK_Agg_Pressure PRIMARY KEY (time_key, zone_key)
);
GO

WITH grid AS (
    SELECT t.time_key, t.is_peak_hour, z.zone_key
    FROM dw.Dim_Time t CROSS JOIN dw.Dim_Zone z
    WHERE t.data_split <> 'spill'
),
dem AS (
    SELECT time_key, zone_key,
           SUM(CASE WHEN service_key = 1 THEN demand ELSE 0 END)          AS rides,
           SUM(CASE WHEN service_key = 2 THEN demand ELSE 0 END)          AS orders,
           SUM(CASE WHEN service_key = 1 THEN lost_no_partner ELSE 0 END) AS lost_rides,
           SUM(CASE WHEN service_key = 2 THEN lost_no_partner ELSE 0 END) AS lost_orders
    FROM dw.vw_Marketplace_ZoneHour
    GROUP BY time_key, zone_key
),
sup AS (
    SELECT time_key, zone_key,
           SUM(partner_hours)                                              AS partners,
           SUM(CASE WHEN vehicle_key = 1 THEN partner_hours ELSE 0 END)    AS two_wheelers
    FROM dw.vw_Supply_ZoneHour
    GROUP BY time_key, zone_key
),
base AS (
    SELECT g.time_key, g.zone_key, g.is_peak_hour,
           ISNULL(d.rides, 0) AS rides, ISNULL(d.orders, 0) AS orders,
           ISNULL(d.lost_rides, 0) AS lost_rides, ISNULL(d.lost_orders, 0) AS lost_orders,
           ISNULL(s.partners, 0) AS partners, ISNULL(s.two_wheelers, 0) AS two_wheelers,
           ISNULL(d.rides, 0) / 2.0 + ISNULL(d.orders, 0) / 3.0 AS work
    FROM grid g
    LEFT JOIN dem d ON d.time_key = g.time_key AND d.zone_key = g.zone_key
    LEFT JOIN sup s ON s.time_key = g.time_key AND s.zone_key = g.zone_key
),
dist AS (
    SELECT a.zone_key AS from_zone, b.zone_key AS to_zone,
           CASE WHEN a.zone_key = b.zone_key THEN 0.0
                ELSE geography::Point(a.latitude, a.longitude, 4326)
                       .STDistance(geography::Point(b.latitude, b.longitude, 4326)) / 1000.0 * 1.4
           END AS km
    FROM dw.Dim_Zone a CROSS JOIN dw.Dim_Zone b
),
nbhd AS (
    SELECT b.time_key, b.zone_key, SUM(n.work) AS nbhd_work, SUM(n.partners) AS nbhd_supply
    FROM base b
    JOIN dist d ON d.from_zone = b.zone_key
               AND d.km <= CASE WHEN b.is_peak_hour = 1 THEN 5.0 ELSE 25.0 / 3 END
    JOIN base n ON n.time_key = b.time_key AND n.zone_key = d.to_zone
    GROUP BY b.time_key, b.zone_key
),
city AS (
    SELECT time_key, SUM(work) AS city_work, SUM(partners) AS city_supply
    FROM base GROUP BY time_key
),
calc AS (
    SELECT b.*, nb.nbhd_work, nb.nbhd_supply, c.city_work, c.city_supply,
           CASE WHEN b.partners > 0 THEN b.work / b.partners END                 AS local_mpi,
           CASE WHEN nb.nbhd_supply > 0 THEN nb.nbhd_work / nb.nbhd_supply END   AS nbhd_mpi,
           CASE WHEN c.city_supply > 0 THEN c.city_work / c.city_supply END      AS city_mpi
    FROM base b
    JOIN nbhd nb ON nb.time_key = b.time_key AND nb.zone_key = b.zone_key
    JOIN city c  ON c.time_key = b.time_key
)
INSERT INTO dw.Agg_Pressure_ZoneHour
    (time_key, zone_key, ride_requests, food_orders, lost_rides, lost_orders, work_hours,
     supply_hours, two_wheeler_hours, local_mpi, nbhd_work_hours, nbhd_supply_hours, nbhd_mpi,
     city_mpi, mobility_mpi, food_mpi, pressure_state, shortage_type)
SELECT time_key, zone_key, rides, orders, lost_rides, lost_orders, work,
       partners, two_wheelers, local_mpi, nbhd_work, nbhd_supply, nbhd_mpi, city_mpi,
       CASE WHEN partners > 0 THEN rides / (2.0 * partners) END,
       CASE WHEN two_wheelers > 0 THEN orders / (3.0 * two_wheelers) END,
       CASE WHEN work = 0 AND partners = 0 THEN 'No activity'
            WHEN local_mpi IS NULL OR local_mpi > 1.10 THEN 'Under-supplied'
            WHEN local_mpi < 0.80 THEN 'Over-supplied'
            ELSE 'Balanced' END,
       CASE WHEN NOT (work > 0 AND (local_mpi IS NULL OR local_mpi > 1.10)) THEN 'None'
            WHEN nbhd_mpi IS NOT NULL AND nbhd_mpi <= 1.10 THEN 'Fix now'
            WHEN city_mpi IS NOT NULL AND city_mpi <= 1.10 THEN 'Reposition ahead'
            ELSE 'Citywide shortage' END
FROM calc;
GO

CREATE INDEX IX_Pressure_Zone ON dw.Agg_Pressure_ZoneHour (zone_key) INCLUDE (pressure_state, shortage_type, local_mpi);
GO
