/* =========================================================================
   PULSE Phase 11 - 00: incentive and stress-scenario result tables
   Rebuilt by scripts/report_phase11.py. Phase 10 rows in
   dw.Agg_Policy_ZoneHour are kept; only Phase 11 scenario codes are replaced.
   ========================================================================= */
USE PULSE_DW;
GO

DELETE FROM dw.Fact_Incentives;
DELETE FROM dw.Agg_Policy_ZoneHour WHERE scenario_code LIKE 'incentive[_]%';
DROP TABLE IF EXISTS dw.Agg_Scenario_Summary;
GO

CREATE TABLE dw.Agg_Scenario_Summary (            -- one row per simulated study run
    study                    VARCHAR(20)   NOT NULL,   -- incentive | stress
    scenario_code            VARCHAR(60)   NOT NULL,
    stress_case              VARCHAR(30)   NOT NULL,
    policy                   VARCHAR(30)   NOT NULL,
    bonus                    DECIMAL(8,2)  NOT NULL,   -- INR per incentive partner-hour (0 = none)
    days                     INT           NOT NULL,
    requests                 INT           NOT NULL,
    completed                INT           NOT NULL,
    lost_no_partner          INT           NOT NULL,
    revenue                  DECIMAL(14,2) NOT NULL,
    reposition_cost          DECIMAL(14,2) NOT NULL,
    incentive_partner_hours  INT           NOT NULL,   -- per weekday
    incentive_cost           DECIMAL(14,2) NOT NULL,
    contribution             DECIMAL(14,2) NOT NULL,   -- revenue - repositioning - incentives
    CONSTRAINT PK_Scenario_Summary PRIMARY KEY (study, scenario_code)
);
GO
