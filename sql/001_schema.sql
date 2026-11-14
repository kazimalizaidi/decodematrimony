/* 🎀 DecodeMatrimony schema (SQL Server). Idempotent: safe to re-run. ✨
   Layers: stg (disposable landing) -> core (validated) -> ana (results) | ops (lineage). 🧸 */
IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
GO
IF SCHEMA_ID('core') IS NULL EXEC('CREATE SCHEMA core');
GO
IF SCHEMA_ID('ana') IS NULL EXEC('CREATE SCHEMA ana');
GO
IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');
GO
/* 🌸 ops: every run and every source file is traceable */
IF OBJECT_ID('ops.run_log') IS NULL
CREATE TABLE ops.run_log (
    run_id        UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_run_log PRIMARY KEY,
    started_at    DATETIME2(0)     NOT NULL,
    finished_at   DATETIME2(0)     NULL,
    status        VARCHAR(12)      NOT NULL CONSTRAINT CK_run_status CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
    n_boot        INT              NOT NULL,
    seed          INT              NOT NULL,
    message       NVARCHAR(1000)   NULL
);
GO
IF OBJECT_ID('ops.data_lineage') IS NULL
CREATE TABLE ops.data_lineage (
    source_name   VARCHAR(100)  NOT NULL,
    file_sha256   CHAR(64)      NOT NULL,
    n_rows        INT           NOT NULL,
    loaded_at     DATETIME2(0)  NOT NULL,
    CONSTRAINT PK_data_lineage PRIMARY KEY (source_name, file_sha256)
);
GO
/* 💗 core.couples: one row per DHS couple, survey design columns kept for inference */
IF OBJECT_ID('core.couples') IS NULL
CREATE TABLE core.couples (
    couple_id            VARCHAR(60)  NOT NULL CONSTRAINT PK_couples PRIMARY KEY,
    survey_year          SMALLINT     NOT NULL,
    weight               FLOAT        NOT NULL CONSTRAINT CK_c_weight CHECK (weight > 0),
    psu                  INT          NOT NULL,
    strata               INT          NOT NULL,
    wife_age             TINYINT      NULL CONSTRAINT CK_c_wage CHECK (wife_age BETWEEN 15 AND 99),
    husband_age          TINYINT      NULL CONSTRAINT CK_c_hage CHECK (husband_age BETWEEN 15 AND 99),
    age_gap              SMALLINT     NULL CONSTRAINT CK_c_gap CHECK (age_gap BETWEEN -40 AND 60),
    wife_edu             TINYINT      NULL CONSTRAINT CK_c_wedu CHECK (wife_edu BETWEEN 0 AND 3),
    husband_edu          TINYINT      NULL CONSTRAINT CK_c_hedu CHECK (husband_edu BETWEEN 0 AND 3),
    edu_pairing          VARCHAR(12)  NULL CONSTRAINT CK_c_pair CHECK (edu_pairing IN ('hypergamous','homogamous','hypogamous')),
    wealth_quintile      TINYINT      NULL CONSTRAINT CK_c_wealth CHECK (wealth_quintile BETWEEN 1 AND 5),
    region               VARCHAR(60)  NULL,
    wife_age_first_union TINYINT      NULL CONSTRAINT CK_c_afu CHECK (wife_age_first_union BETWEEN 8 AND 60),
    wife_working         BIT          NULL,
    wife_ethnicity       VARCHAR(60)  NULL,
    husband_ethnicity    VARCHAR(60)  NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_couples_region_edu')
CREATE INDEX IX_couples_region_edu ON core.couples (region, wife_edu) INCLUDE (age_gap, weight, psu, strata);
GO
/* 🧸 Macro series: real public series supplied by the user (SBP/PBS exports) */
IF OBJECT_ID('core.macro_series') IS NULL
CREATE TABLE core.macro_series (
    series_name VARCHAR(40)   NOT NULL,
    obs_date    DATE          NOT NULL,
    value       FLOAT         NOT NULL,
    source      VARCHAR(200)  NOT NULL,
    CONSTRAINT PK_macro PRIMARY KEY (series_name, obs_date)
);
GO
/* 📉 ana.results: every estimate with CI, raw + Holm-adjusted p, and method text */
IF OBJECT_ID('ana.results') IS NULL
CREATE TABLE ana.results (
    run_id        UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_results_run REFERENCES ops.run_log(run_id),
    metric        VARCHAR(80)   NOT NULL,
    group_label   VARCHAR(80)   NOT NULL,
    estimate      FLOAT         NULL,
    ci_low        FLOAT         NULL,
    ci_high       FLOAT         NULL,
    p_value       FLOAT         NULL,
    p_adjusted    FLOAT         NULL,
    n_unweighted  INT           NOT NULL,
    significant   BIT           NOT NULL,
    method        VARCHAR(200)  NOT NULL,
    notes         NVARCHAR(500) NULL,
    CONSTRAINT PK_results PRIMARY KEY (run_id, metric, group_label)
);
GO
/* 🎀 ana.mahr_benchmark: DERIVED gold/CPI benchmark. NOT observed Mahr data! */
IF OBJECT_ID('ana.mahr_benchmark') IS NULL
CREATE TABLE ana.mahr_benchmark (
    obs_date             DATE  NOT NULL CONSTRAINT PK_mahr PRIMARY KEY,
    gold_index           FLOAT NOT NULL,
    cpi_index            FLOAT NOT NULL,
    gold_to_cpi_ratio    FLOAT NOT NULL,
    real_value_fixed_pkr FLOAT NOT NULL
);
GO
CREATE OR ALTER VIEW ana.vw_latest_results AS
SELECT r.* FROM ana.results r
WHERE r.run_id = (SELECT TOP 1 run_id FROM ops.run_log WHERE status='SUCCESS' ORDER BY finished_at DESC);
GO
