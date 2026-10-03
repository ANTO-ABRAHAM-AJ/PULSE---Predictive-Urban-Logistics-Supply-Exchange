/* =========================================================================
   PULSE Phase 8 - 01: Does the Marketplace Pressure Index predict failure?
   Result Set A: zone-hours, demand and lost jobs by pressure state
   Result Set B: loss rate by MPI band (calibration)
   All 112 days; built on dw.Agg_Pressure_ZoneHour.
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
WITH s AS (
    SELECT pressure_state,
           COUNT(*) AS zone_hours,
           SUM(ride_requests + food_orders) AS demand,
           SUM(lost_rides + lost_orders) AS lost
    FROM dw.Agg_Pressure_ZoneHour
    GROUP BY pressure_state
)
SELECT pressure_state                                                    AS [Pressure state],
       zone_hours                                                        AS [Zone-hours],
       CAST(100.0 * zone_hours / SUM(zone_hours) OVER () AS DECIMAL(5,1)) AS [Share of zone-hours %],
       CAST(100.0 * demand / SUM(demand) OVER () AS DECIMAL(5,1))        AS [Share of demand %],
       lost                                                              AS [Jobs lost],
       CAST(100.0 * lost / SUM(lost) OVER () AS DECIMAL(5,1))            AS [Share of lost jobs %],
       CAST(100.0 * lost / NULLIF(demand, 0) AS DECIMAL(5,1))            AS [Loss rate %]
FROM s
ORDER BY CASE pressure_state WHEN 'Over-supplied' THEN 1 WHEN 'Balanced' THEN 2
                             WHEN 'Under-supplied' THEN 3 ELSE 4 END;

/* ---- Result Set B ------------------------------------------------------- */
WITH banded AS (
    SELECT CASE WHEN local_mpi IS NULL THEN 8
                WHEN local_mpi < 0.5 THEN 1 WHEN local_mpi < 0.8 THEN 2
                WHEN local_mpi <= 1.1 THEN 3 WHEN local_mpi < 1.5 THEN 4
                WHEN local_mpi < 2.0 THEN 5 WHEN local_mpi < 3.0 THEN 6 ELSE 7 END AS band,
           ride_requests + food_orders AS demand,
           lost_rides + lost_orders AS lost
    FROM dw.Agg_Pressure_ZoneHour
    WHERE ride_requests + food_orders > 0
)
SELECT CASE band WHEN 1 THEN '< 0.5' WHEN 2 THEN '0.5 - 0.8' WHEN 3 THEN '0.8 - 1.1'
                 WHEN 4 THEN '1.1 - 1.5' WHEN 5 THEN '1.5 - 2.0' WHEN 6 THEN '2.0 - 3.0'
                 WHEN 7 THEN '3.0 or more' ELSE 'No supply present' END   AS [MPI band],
       COUNT(*)                                                          AS [Zone-hours],
       SUM(demand)                                                       AS [Demand],
       SUM(lost)                                                         AS [Jobs lost],
       CAST(100.0 * SUM(lost) / SUM(demand) AS DECIMAL(5,1))             AS [Loss rate %]
FROM banded
GROUP BY band
ORDER BY band;
