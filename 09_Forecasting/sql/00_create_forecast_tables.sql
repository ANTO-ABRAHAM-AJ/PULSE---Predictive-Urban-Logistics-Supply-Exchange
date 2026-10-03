/* =========================================================================
   PULSE Phase 9 - 00: forecast tables (holdout weeks 13-16)
   Rebuilt by scripts/report_phase9.py; read by Phase 10 and Power BI.
   ========================================================================= */
USE PULSE_DW;
GO

DROP TABLE IF EXISTS dw.Fact_Demand_Forecast;
DROP TABLE IF EXISTS dw.Fact_Supply_Forecast;
DROP TABLE IF EXISTS dw.Fact_Pressure_Forecast;
GO

CREATE TABLE dw.Fact_Demand_Forecast (
    time_key          INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key          SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    service_key       TINYINT      NOT NULL REFERENCES dw.Dim_Service(service_key),
    model_name        VARCHAR(30)  NOT NULL,
    forecast_demand   DECIMAL(9,3) NOT NULL,
    actual_demand     INT          NOT NULL,
    CONSTRAINT PK_Demand_Forecast PRIMARY KEY (time_key, zone_key, service_key, model_name)
);

CREATE TABLE dw.Fact_Supply_Forecast (             -- partners online, by HOME zone
    time_key          INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key          SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    vehicle_key       TINYINT      NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    model_name        VARCHAR(30)  NOT NULL,
    forecast_partners DECIMAL(9,3) NOT NULL,
    actual_partners   INT          NOT NULL,
    CONSTRAINT PK_Supply_Forecast PRIMARY KEY (time_key, zone_key, vehicle_key, model_name)
);

CREATE TABLE dw.Fact_Pressure_Forecast (           -- week-ahead pressure prediction
    time_key              INT          NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key              SMALLINT     NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    forecast_work_hours   DECIMAL(9,3) NOT NULL,
    forecast_supply_hours DECIMAL(9,3) NOT NULL,
    forecast_mpi          DECIMAL(9,3) NULL,
    predicted_short       BIT          NOT NULL,
    actual_short          BIT          NOT NULL,
    lost_jobs             INT          NOT NULL,
    CONSTRAINT PK_Pressure_Forecast PRIMARY KEY (time_key, zone_key)
);
GO
