/* =========================================================================
   PULSE Phase 10 - 00: policy result tables (holdout weeks 13-16)
   Rebuilt by scripts/report_phase10.py. Fact_Supply_Allocation and
   Fact_Repositioning were created empty in Phase 4 for this phase.
   ========================================================================= */
USE PULSE_DW;
GO

DELETE FROM dw.Fact_Supply_Allocation;
DELETE FROM dw.Fact_Repositioning;
DROP TABLE IF EXISTS dw.Agg_Policy_ZoneHour;
DROP TABLE IF EXISTS dw.Agg_Supply_Value;
GO

CREATE TABLE dw.Agg_Policy_ZoneHour (            -- simulated outcome per scenario
    scenario_code       VARCHAR(40)   NOT NULL,
    time_key            INT           NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key            SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    service_key         TINYINT       NOT NULL REFERENCES dw.Dim_Service(service_key),
    requests            INT           NOT NULL,
    completed           INT           NOT NULL,
    lost_no_partner     INT           NOT NULL,
    cancelled_customer  INT           NOT NULL,
    revenue             DECIMAL(12,2) NOT NULL,
    CONSTRAINT PK_Policy_ZoneHour PRIMARY KEY (scenario_code, time_key, zone_key, service_key)
);

CREATE TABLE dw.Agg_Supply_Value (               -- LP shadow price: value of one more partner
    scenario_code       VARCHAR(40)   NOT NULL,
    time_key            INT           NOT NULL REFERENCES dw.Dim_Time(time_key),
    zone_key            SMALLINT      NOT NULL REFERENCES dw.Dim_Zone(zone_key),
    vehicle_key         TINYINT       NOT NULL REFERENCES dw.Dim_Vehicle(vehicle_key),
    shadow_price        DECIMAL(9,2)  NOT NULL,   -- INR per extra partner for that hour
    CONSTRAINT PK_Supply_Value PRIMARY KEY (scenario_code, time_key, zone_key, vehicle_key)
);
GO
