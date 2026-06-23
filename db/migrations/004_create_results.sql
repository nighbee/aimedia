CREATE TABLE IF NOT EXISTS analysis.results (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id                   UUID NOT NULL REFERENCES core.jobs(id) ON DELETE CASCADE,
    illegal_gambling_score   SMALLINT NULL,
    pyramid_scheme_score     SMALLINT NULL,
    investment_fraud_score   SMALLINT NULL,
    referral_scheme_score    SMALLINT NULL,
    top_flags                JSONB NULL,
    extracted_signals        JSONB NULL,
    soniox_job_id            TEXT NULL,
    gemini_pass1_request_id  TEXT NULL,
    gemini_pass2_request_id  TEXT NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_results_job_id ON analysis.results(job_id);
