package model

import (
	"time"

	"github.com/google/uuid"
)

type TopFlag struct {
	Signal string `json:"signal"`
	Weight string `json:"weight"`
}

type ExtractedSignalPhrase struct {
	Text        string `json:"text"`
	TimestampS  int    `json:"timestamp_s"`
	Category    string `json:"category"`
}

type VisualMarker struct {
	FrameIndex  int    `json:"frame_index"`
	Description string `json:"description"`
	Category    string `json:"category"`
}

type Entity struct {
	Name string `json:"name"`
	Type string `json:"type"`
}

type ExtractedSignals struct {
	Phrases       []ExtractedSignalPhrase `json:"phrases"`
	VisualMarkers []VisualMarker          `json:"visual_markers"`
	Entities      []Entity                `json:"entities"`
}

type AnalysisResult struct {
	ID                   uuid.UUID         `json:"id" db:"id"`
	JobID                uuid.UUID         `json:"job_id" db:"job_id"`
	IllegalGamblingScore *int              `json:"illegal_gambling_score" db:"illegal_gambling_score"`
	PyramidSchemeScore   *int              `json:"pyramid_scheme_score" db:"pyramid_scheme_score"`
	InvestmentFraudScore *int              `json:"investment_fraud_score" db:"investment_fraud_score"`
	ReferralSchemeScore  *int              `json:"referral_scheme_score" db:"referral_scheme_score"`
	TopFlags             *[]TopFlag        `json:"top_flags" db:"top_flags"`
	ExtractedSignals     *ExtractedSignals `json:"extracted_signals" db:"extracted_signals"`
	SonioxJobID          *string           `json:"soniox_job_id" db:"soniox_job_id"`
	GeminiPass1RequestID *string           `json:"gemini_pass1_request_id" db:"gemini_pass1_request_id"`
	GeminiPass2RequestID *string           `json:"gemini_pass2_request_id" db:"gemini_pass2_request_id"`
	CreatedAt            time.Time         `json:"created_at" db:"created_at"`
}

type JobDetailResponse struct {
	Job      Job             `json:"job"`
	Analysis *AnalysisResult `json:"analysis,omitempty"`
}
