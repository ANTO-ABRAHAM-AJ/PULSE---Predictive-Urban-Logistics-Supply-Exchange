/* =========================================================================
   PULSE Data Warehouse - 01: create the database and schema
   Run against: master.  Safe to re-run.
   ========================================================================= */
IF DB_ID(N'PULSE_DW') IS NULL
    CREATE DATABASE PULSE_DW;
GO

USE PULSE_DW;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'dw')
    EXEC (N'CREATE SCHEMA dw AUTHORIZATION dbo;');
GO
