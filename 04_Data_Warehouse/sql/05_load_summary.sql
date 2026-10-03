/* =========================================================================
   PULSE Data Warehouse - 05: load summary (row count per table)
   Used by scripts/report_warehouse.py; also handy to run in SSMS.
   ========================================================================= */
USE PULSE_DW;

SELECT t.name                    AS table_name,
       CASE WHEN t.name LIKE 'Dim%' THEN 'Dimension' ELSE 'Fact' END AS table_role,
       SUM(p.rows)               AS row_count
FROM sys.tables t
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE SCHEMA_NAME(t.schema_id) = 'dw'
GROUP BY t.name
ORDER BY table_role, t.name;
