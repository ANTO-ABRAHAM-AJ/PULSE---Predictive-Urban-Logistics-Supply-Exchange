/* =========================================================================
   PULSE Phase 9 - 05: can we see shortages a week ahead?
   Result Set A: predicted vs actual under-supplied zone-hours, with lost jobs
   Result Set B: by zone type — precision, recall and lost jobs captured
   Holdout weeks 13-16. "Short" = Under-supplied (MPI > 1.10, Phase 8).
   ========================================================================= */
USE PULSE_DW;

/* ---- Result Set A ------------------------------------------------------- */
SELECT CASE WHEN predicted_short = 1 THEN 'Predicted short' ELSE 'Predicted not short' END AS [Prediction],
       SUM(CASE WHEN actual_short = 1 THEN 1 ELSE 0 END)                                   AS [Actually short],
       SUM(CASE WHEN actual_short = 0 THEN 1 ELSE 0 END)                                   AS [Actually not short],
       SUM(lost_jobs)                                                                      AS [Jobs lost],
       CAST(100.0 * SUM(lost_jobs) / SUM(SUM(lost_jobs)) OVER () AS DECIMAL(5,1))          AS [Share of lost jobs %]
FROM dw.Fact_Pressure_Forecast
GROUP BY predicted_short
ORDER BY predicted_short DESC;

/* ---- Result Set B ------------------------------------------------------- */
SELECT z.zone_type                                                                         AS [Zone type],
       SUM(CAST(f.actual_short AS INT))                                                    AS [Actually short],
       SUM(CAST(f.predicted_short AS INT))                                                 AS [Predicted short],
       SUM(CASE WHEN f.actual_short = 1 AND f.predicted_short = 1 THEN 1 ELSE 0 END)       AS [Correctly predicted],
       CAST(100.0 * SUM(CASE WHEN f.actual_short = 1 AND f.predicted_short = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CAST(f.predicted_short AS INT)), 0) AS DECIMAL(5,1))             AS [Precision %],
       CAST(100.0 * SUM(CASE WHEN f.actual_short = 1 AND f.predicted_short = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CAST(f.actual_short AS INT)), 0) AS DECIMAL(5,1))                AS [Recall %],
       CAST(100.0 * SUM(CASE WHEN f.predicted_short = 1 THEN f.lost_jobs ELSE 0 END)
            / NULLIF(SUM(f.lost_jobs), 0) AS DECIMAL(5,1))                                AS [Lost jobs captured %]
FROM dw.Fact_Pressure_Forecast f
JOIN dw.Dim_Zone z ON z.zone_key = f.zone_key
GROUP BY z.zone_type
ORDER BY [Lost jobs captured %] DESC;
