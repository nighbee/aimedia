package service

import (
	"context"

	"github.com/google/uuid"

	"github.com/aimedia/api-gateway/internal/model"
	"github.com/aimedia/api-gateway/internal/storage"
)

type JobService interface {
	SubmitJob(ctx context.Context, req model.CreateJobRequest, inspectorID *uuid.UUID) (*model.Job, error)
	GetJob(ctx context.Context, id uuid.UUID) (*model.Job, *model.AnalysisResult, error)
	ListJobs(ctx context.Context, params model.ListJobsParams) (*model.JobListResponse, error)
	UpdateJobStatus(ctx context.Context, id uuid.UUID, status model.JobStatus) error
	GetEvidenceURL(ctx context.Context, id uuid.UUID) (*string, error)
	SetS3Client(s3 *storage.S3Client)
}
