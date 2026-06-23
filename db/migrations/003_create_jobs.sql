CREATE TABLE IF NOT EXISTS core.jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url             TEXT NOT NULL,
    platform        VARCHAR(32) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority        SMALLINT NOT NULL DEFAULT 2,
    risk_score      SMALLINT NULL,
    confidence      VARCHAR(16) NULL,
    reasoning       TEXT NULL,
    evidence_url    TEXT NULL,
    failed_at_stage VARCHAR(32) NULL,
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    inspector_id    UUID REFERENCES core.users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON core.jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_risk_score ON core.jobs(risk_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_inspector ON core.jobs(inspector_id);
