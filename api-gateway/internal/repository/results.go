package repository

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/aimedia/api-gateway/internal/model"
)

var ErrResultNotFound = errors.New("analysis result not found")

type ResultRepository struct {
	pool *pgxpool.Pool
}

func NewResultRepository(pool *pgxpool.Pool) *ResultRepository {
	return &ResultRepository{pool: pool}
}

func (r *ResultRepository) Upsert(ctx context.Context, result *model.AnalysisResult) error {
	query := `
		INSERT INTO analysis.results (
			id, job_id, illegal_gambling_score, pyramid_scheme_score,
			investment_fraud_score, referral_scheme_score,
			top_flags, extracted_signals, soniox_job_id,
			gemini_pass1_request_id, gemini_pass2_request_id, created_at
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
		ON CONFLICT (job_id) DO UPDATE SET
			illegal_gambling_score = EXCLUDED.illegal_gambling_score,
			pyramid_scheme_score = EXCLUDED.pyramid_scheme_score,
			investment_fraud_score = EXCLUDED.investment_fraud_score,
			referral_scheme_score = EXCLUDED.referral_scheme_score,
			top_flags = EXCLUDED.top_flags,
			extracted_signals = EXCLUDED.extracted_signals,
			soniox_job_id = EXCLUDED.soniox_job_id,
			gemini_pass1_request_id = EXCLUDED.gemini_pass1_request_id,
			gemini_pass2_request_id = EXCLUDED.gemini_pass2_request_id`

	result.ID = uuid.New()
	result.CreatedAt = time.Now().UTC()

	topFlagsJSON, err := json.Marshal(result.TopFlags)
	if err != nil {
		return err
	}
	signalsJSON, err := json.Marshal(result.ExtractedSignals)
	if err != nil {
		return err
	}

	_, err = r.pool.Exec(ctx, query,
		result.ID, result.JobID,
		result.IllegalGamblingScore, result.PyramidSchemeScore,
		result.InvestmentFraudScore, result.ReferralSchemeScore,
		topFlagsJSON, signalsJSON,
		result.SonioxJobID, result.GeminiPass1RequestID, result.GeminiPass2RequestID,
		result.CreatedAt,
	)
	return err
}

func (r *ResultRepository) FindByJobID(ctx context.Context, jobID uuid.UUID) (*model.AnalysisResult, error) {
	query := `
		SELECT id, job_id, illegal_gambling_score, pyramid_scheme_score,
		       investment_fraud_score, referral_scheme_score,
		       top_flags, extracted_signals, soniox_job_id,
		       gemini_pass1_request_id, gemini_pass2_request_id, created_at
		FROM analysis.results WHERE job_id = $1`

	result := &model.AnalysisResult{}
	var topFlagsJSON, signalsJSON []byte

	err := r.pool.QueryRow(ctx, query, jobID).Scan(
		&result.ID, &result.JobID,
		&result.IllegalGamblingScore, &result.PyramidSchemeScore,
		&result.InvestmentFraudScore, &result.ReferralSchemeScore,
		&topFlagsJSON, &signalsJSON,
		&result.SonioxJobID, &result.GeminiPass1RequestID, &result.GeminiPass2RequestID,
		&result.CreatedAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrResultNotFound
	}
	if err != nil {
		return nil, err
	}

	if len(topFlagsJSON) > 0 {
		flags := []model.TopFlag{}
		if err := json.Unmarshal(topFlagsJSON, &flags); err != nil {
			return nil, err
		}
		result.TopFlags = &flags
	}
	if len(signalsJSON) > 0 {
		signals := model.ExtractedSignals{}
		if err := json.Unmarshal(signalsJSON, &signals); err != nil {
			return nil, err
		}
		result.ExtractedSignals = &signals
	}

	return result, nil
}
