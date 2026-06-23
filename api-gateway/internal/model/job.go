package model

import (
	"time"

	"github.com/google/uuid"
)

type JobStatus string

const (
	JobStatusPending          JobStatus = "pending"
	JobStatusDownloading      JobStatus = "downloading"
	JobStatusExtracting       JobStatus = "extracting"
	JobStatusAnalyzing        JobStatus = "analyzing"
	JobStatusAggregating      JobStatus = "aggregating"
	JobStatusGeneratingEvidence JobStatus = "generating_evidence"
	JobStatusCompleted        JobStatus = "completed"
	JobStatusFailed           JobStatus = "failed"
)

type Job struct {
	ID            uuid.UUID  `json:"job_id" db:"id"`
	URL           string     `json:"url" db:"url"`
	Platform      string     `json:"platform" db:"platform"`
	Status        JobStatus  `json:"status" db:"status"`
	Priority      int        `json:"priority" db:"priority"`
	RiskScore     *int       `json:"risk_score,omitempty" db:"risk_score"`
	Confidence    *string    `json:"confidence,omitempty" db:"confidence"`
	Reasoning     *string    `json:"reasoning,omitempty" db:"reasoning"`
	EvidenceURL   *string    `json:"evidence_url,omitempty" db:"evidence_url"`
	CustodyLog    interface{} `json:"custody_log,omitempty" db:"custody_log"`
	FailedAtStage *string    `json:"failed_at_stage,omitempty" db:"failed_at_stage"`
	RetryCount    int        `json:"retry_count" db:"retry_count"`
	InspectorID   *uuid.UUID `json:"inspector_id,omitempty" db:"inspector_id"`
	CreatedAt     time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at" db:"updated_at"`
	CompletedAt   *time.Time `json:"completed_at,omitempty" db:"completed_at"`
}

type CreateJobRequest struct {
	URL       string `json:"url"`
	Platform  string `json:"platform,omitempty"`
	Priority  int    `json:"priority,omitempty"`
}

const (
	MaxURLLength      = 2048
	MinPriority       = 1
	MaxPriority       = 3
	DefaultPriority   = 2
)

type UpdateStatusRequest struct {
	Status string `json:"status"`
}

type JobCompletedEvent struct {
	JobID       string             `json:"job_id"`
	Status      string             `json:"status"`
	RiskScore   *int               `json:"risk_score"`
	Confidence  *string            `json:"confidence"`
	Reasoning   *string            `json:"reasoning"`
	Categories  *map[string]int    `json:"categories"`
	TopFlags    *[]TopFlag         `json:"top_flags"`
	EvidenceURL *string            `json:"evidence_url"`
	CustodyLog  interface{}        `json:"custody_log"`
	Error       *string            `json:"error"`
}

type ListJobsParams struct {
	Status string
	Page   int
	Limit  int
	SortBy string
}

type JobListResponse struct {
	Jobs       []Job `json:"jobs"`
	Total      int   `json:"total"`
	Page       int   `json:"page"`
	Limit      int   `json:"limit"`
	TotalPages int   `json:"total_pages"`
}

const (
	DefaultPage     = 1
	DefaultPageSize = 20
	MaxPageSize     = 100
)
