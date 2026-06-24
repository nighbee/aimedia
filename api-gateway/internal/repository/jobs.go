package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/aimedia/api-gateway/internal/model"
)

var (
	ErrNotFound = errors.New("job not found")
)

type JobRepository struct {
	pool *pgxpool.Pool
}

func NewJobRepository(pool *pgxpool.Pool) *JobRepository {
	return &JobRepository{pool: pool}
}

func (r *JobRepository) Create(ctx context.Context, job *model.Job) error {
	query := `
		INSERT INTO core.jobs (id, url, platform, status, priority, inspector_id, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`

	now := time.Now().UTC()
	job.ID = uuid.New()
	job.Status = model.JobStatusPending
	job.CreatedAt = now
	job.UpdatedAt = now

	var inspectorID interface{}
	if job.InspectorID != nil {
		inspectorID = *job.InspectorID
	}

	_, err := r.pool.Exec(ctx, query,
		job.ID, job.URL, job.Platform, job.Status, job.Priority, inspectorID, job.CreatedAt, job.UpdatedAt,
	)
	return err
}

func (r *JobRepository) FindByID(ctx context.Context, id uuid.UUID) (*model.Job, error) {
	query := `
		SELECT id, url, platform, status, priority, risk_score, confidence, reasoning,
		       evidence_url, custody_log, failed_at_stage, retry_count, inspector_id,
		       created_at, updated_at, completed_at
		FROM core.jobs WHERE id = $1`

	job := &model.Job{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&job.ID, &job.URL, &job.Platform, &job.Status, &job.Priority,
		&job.RiskScore, &job.Confidence, &job.Reasoning,
		&job.EvidenceURL, &job.CustodyLog, &job.FailedAtStage, &job.RetryCount, &job.InspectorID,
		&job.CreatedAt, &job.UpdatedAt, &job.CompletedAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return job, err
}

func (r *JobRepository) List(ctx context.Context, statusFilter string) ([]model.Job, error) {
	query := `
		SELECT id, url, platform, status, priority, risk_score, confidence, reasoning,
		       evidence_url, custody_log, failed_at_stage, retry_count, inspector_id,
		       created_at, updated_at, completed_at
		FROM core.jobs`
	args := []interface{}{}

	if statusFilter != "" {
		query += " WHERE status = $1"
		args = append(args, statusFilter)
	}
	query += " ORDER BY risk_score DESC NULLS LAST, created_at DESC"

	return r.queryJobs(ctx, query, args...)
}

func (r *JobRepository) Count(ctx context.Context, statusFilter string) (int, error) {
	query := `SELECT COUNT(*) FROM core.jobs`
	args := []interface{}{}

	if statusFilter != "" {
		query += " WHERE status = $1"
		args = append(args, statusFilter)
	}

	var count int
	err := r.pool.QueryRow(ctx, query, args...).Scan(&count)
	return count, err
}

func (r *JobRepository) ListPaginated(ctx context.Context, params model.ListJobsParams) ([]model.Job, int, error) {
	total, err := r.Count(ctx, params.Status)
	if err != nil {
		return nil, 0, err
	}

	offset := (params.Page - 1) * params.Limit
	query := `
		SELECT id, url, platform, status, priority, risk_score, confidence, reasoning,
		       evidence_url, custody_log, failed_at_stage, retry_count, inspector_id,
		       created_at, updated_at, completed_at
		FROM core.jobs`
	args := []interface{}{}
	argIdx := 1

	if params.Status != "" {
		query += " WHERE status = $" + itoa(argIdx)
		args = append(args, params.Status)
		argIdx++
	}

	switch params.SortBy {
	case "created_at":
		query += " ORDER BY created_at DESC"
	case "risk_score":
		query += " ORDER BY risk_score DESC NULLS LAST"
	default:
		query += " ORDER BY risk_score DESC NULLS LAST, created_at DESC"
	}

	query += " LIMIT $" + itoa(argIdx) + " OFFSET $" + itoa(argIdx+1)
	args = append(args, params.Limit, offset)

	jobs, err := r.queryJobs(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	return jobs, total, nil
}

func itoa(i int) string {
	return fmt.Sprintf("%d", i)
}

func (r *JobRepository) queryJobs(ctx context.Context, query string, args ...interface{}) ([]model.Job, error) {
	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []model.Job
	for rows.Next() {
		var j model.Job
		if err := rows.Scan(
			&j.ID, &j.URL, &j.Platform, &j.Status, &j.Priority,
			&j.RiskScore, &j.Confidence, &j.Reasoning,
			&j.EvidenceURL, &j.CustodyLog, &j.FailedAtStage, &j.RetryCount, &j.InspectorID,
			&j.CreatedAt, &j.UpdatedAt, &j.CompletedAt,
		); err != nil {
			return nil, err
		}
		jobs = append(jobs, j)
	}
	return jobs, rows.Err()
}

func (r *JobRepository) UpdateStatus(ctx context.Context, id uuid.UUID, status model.JobStatus, failedAtStage *string, custodyLog interface{}) error {
	query := `
		UPDATE core.jobs
		SET status = $1, failed_at_stage = $2, custody_log = COALESCE($3, custody_log),
		    updated_at = $4
		WHERE id = $5`
	result, err := r.pool.Exec(ctx, query, status, failedAtStage, custodyLog, time.Now().UTC(), id)
	if err != nil {
		return err
	}
	if result.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *JobRepository) Complete(ctx context.Context, id uuid.UUID, riskScore int, confidence string, reasoning string, evidenceURL *string, custodyLog interface{}) error {
	query := `
		UPDATE core.jobs
		SET status = $1, risk_score = $2, confidence = $3, reasoning = $4,
		    evidence_url = COALESCE($5, evidence_url),
		    custody_log = COALESCE($6, custody_log),
		    completed_at = $7, updated_at = $7
		WHERE id = $8`
	now := time.Now().UTC()
	result, err := r.pool.Exec(ctx, query,
		model.JobStatusCompleted, riskScore, confidence, reasoning, evidenceURL, custodyLog, now, id,
	)
	if err != nil {
		return err
	}
	if result.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *JobRepository) UpdateEvidenceURL(ctx context.Context, id uuid.UUID, evidenceURL string) error {
	query := `
		UPDATE core.jobs
		SET evidence_url = $1, updated_at = $2
		WHERE id = $3`
	result, err := r.pool.Exec(ctx, query, evidenceURL, time.Now().UTC(), id)
	if err != nil {
		return err
	}
	if result.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
