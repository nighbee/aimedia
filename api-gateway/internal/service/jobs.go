package service

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"

	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/aimedia/api-gateway/internal/model"
	"github.com/aimedia/api-gateway/internal/queue"
	"github.com/aimedia/api-gateway/internal/repository"
	"github.com/aimedia/api-gateway/internal/storage"
)

var (
	ErrInvalidURL       = errors.New("invalid or unsupported URL: only tiktok.com and instagram.com URLs with http/https scheme are allowed")
	ErrPlatformMismatch = errors.New("platform does not match the submitted URL")
	ErrInvalidPriority  = errors.New("priority must be between 1 and 3")
	ErrInvalidStatus    = errors.New("invalid job status")
	ErrInvalidTransition = errors.New("invalid status transition")
	ErrURLTooLong       = fmt.Errorf("url must not exceed %d characters", model.MaxURLLength)
)

var allowedHostSuffixes = []string{
	"tiktok.com",
	"instagram.com",
	"instagr.am",
}

var validTransitions = map[model.JobStatus][]model.JobStatus{
	model.JobStatusPending:            {model.JobStatusDownloading, model.JobStatusFailed},
	model.JobStatusDownloading:        {model.JobStatusExtracting, model.JobStatusFailed},
	model.JobStatusExtracting:         {model.JobStatusAnalyzing, model.JobStatusFailed},
	model.JobStatusAnalyzing:          {model.JobStatusAggregating, model.JobStatusFailed},
	model.JobStatusAggregating:        {model.JobStatusGeneratingEvidence, model.JobStatusCompleted, model.JobStatusFailed},
	model.JobStatusGeneratingEvidence: {model.JobStatusCompleted, model.JobStatusFailed},
	model.JobStatusCompleted:          {},
	model.JobStatusFailed:             {},
}

type jobService struct {
	jobRepo  *repository.JobRepository
	resRepo  *repository.ResultRepository
	producer *queue.Producer
	logger   *zap.Logger
	s3       *storage.S3Client
}

func NewJobService(
	jobRepo *repository.JobRepository,
	resRepo *repository.ResultRepository,
	producer *queue.Producer,
	logger *zap.Logger,
) JobService {
	return &jobService{
		jobRepo:  jobRepo,
		resRepo:  resRepo,
		producer: producer,
		logger:   logger,
	}
}

func (s *jobService) SubmitJob(ctx context.Context, req model.CreateJobRequest, inspectorID uuid.UUID) (*model.Job, error) {
	urlStr := strings.TrimSpace(req.URL)
	if urlStr == "" {
		return nil, ErrInvalidURL
	}
	if len(urlStr) > model.MaxURLLength {
		return nil, ErrURLTooLong
	}

	parsed, err := url.ParseRequestURI(urlStr)
	if err != nil {
		return nil, fmt.Errorf("invalid url: %w", ErrInvalidURL)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, ErrInvalidURL
	}

	hostname := strings.ToLower(parsed.Hostname())
	platform := detectPlatform(hostname)
	if platform == "" {
		return nil, ErrInvalidURL
	}

	// Cross-validate explicit platform field if provided
	if req.Platform != "" {
		reqPlatform := strings.ToLower(strings.TrimSpace(req.Platform))
		if reqPlatform != platform {
			return nil, ErrPlatformMismatch
		}
	}

	priority := req.Priority
	if priority == 0 {
		priority = model.DefaultPriority
	} else if priority < model.MinPriority || priority > model.MaxPriority {
		return nil, ErrInvalidPriority
	}

	job := &model.Job{
		URL:         sanitizeURL(parsed),
		Platform:    platform,
		Priority:    priority,
		InspectorID: inspectorID,
	}

	if err := s.jobRepo.Create(ctx, job); err != nil {
		s.logger.Error("failed to create job", zap.Error(err))
		return nil, errors.New("failed to create job")
	}

	if err := s.producer.PublishJobCreated(ctx, job.ID.String(), job.URL, job.Platform, inspectorID.String(), priority); err != nil {
		s.logger.Error("failed to publish job.created event",
			zap.String("job_id", job.ID.String()),
			zap.Error(err),
		)
		// Job is persisted — the reconciliation loop will retry
	}

	s.logger.Info("job submitted",
		zap.String("job_id", job.ID.String()),
		zap.String("url", job.URL),
		zap.String("platform", platform),
		zap.Int("priority", priority),
	)

	return job, nil
}

func (s *jobService) GetJob(ctx context.Context, id uuid.UUID) (*model.Job, *model.AnalysisResult, error) {
	job, err := s.jobRepo.FindByID(ctx, id)
	if err != nil {
		return nil, nil, err
	}

	result, err := s.resRepo.FindByJobID(ctx, id)
	if err != nil && !errors.Is(err, repository.ErrResultNotFound) {
		s.logger.Error("failed to fetch analysis result", zap.String("job_id", id.String()), zap.Error(err))
	}

	return job, result, nil
}

func (s *jobService) ListJobs(ctx context.Context, params model.ListJobsParams) (*model.JobListResponse, error) {
	if params.Page < 1 {
		params.Page = model.DefaultPage
	}
	if params.Limit < 1 || params.Limit > model.MaxPageSize {
		params.Limit = model.DefaultPageSize
	}

	jobs, total, err := s.jobRepo.ListPaginated(ctx, params)
	if err != nil {
		return nil, err
	}
	if jobs == nil {
		jobs = []model.Job{}
	}

	totalPages := (total + params.Limit - 1) / params.Limit

	return &model.JobListResponse{
		Jobs:       jobs,
		Total:      total,
		Page:       params.Page,
		Limit:      params.Limit,
		TotalPages: totalPages,
	}, nil
}

func (s *jobService) UpdateJobStatus(ctx context.Context, id uuid.UUID, status model.JobStatus) error {
	job, err := s.jobRepo.FindByID(ctx, id)
	if err != nil {
		return err
	}

	if !isValidTransition(job.Status, status) {
		s.logger.Warn("invalid status transition",
			zap.String("job_id", id.String()),
			zap.String("from", string(job.Status)),
			zap.String("to", string(status)),
		)
		return ErrInvalidTransition
	}

	return s.jobRepo.UpdateStatus(ctx, id, status, nil)
}

func (s *jobService) SetS3Client(s3 *storage.S3Client) {
	s.s3 = s3
}

func (s *jobService) GetEvidenceURL(ctx context.Context, id uuid.UUID) (*string, error) {
	job, err := s.jobRepo.FindByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if job.EvidenceURL == nil || *job.EvidenceURL == "" {
		return nil, nil
	}

	// If S3 client is available, regenerate a presigned URL from the stored object path
	if s.s3 != nil {
		presignedURL, err := s.s3.PresignedURL(ctx, *job.EvidenceURL)
		if err != nil {
			s.logger.Error("failed to generate presigned URL, falling back to stored URL",
				zap.String("job_id", id.String()),
				zap.Error(err),
			)
			return job.EvidenceURL, nil
		}
		return presignedURL, nil
	}

	return job.EvidenceURL, nil
}

func detectPlatform(hostname string) string {
	for _, suffix := range allowedHostSuffixes {
		if hostname == suffix || strings.HasSuffix(hostname, "."+suffix) {
			switch suffix {
			case "tiktok.com":
				return "tiktok"
			case "instagram.com", "instagr.am":
				return "instagram"
			}
		}
	}
	return ""
}

func sanitizeURL(parsed *url.URL) string {
	// Strip fragment, normalize
	parsed.Fragment = ""
	return parsed.String()
}

func isValidTransition(from, to model.JobStatus) bool {
	allowed, ok := validTransitions[from]
	if !ok {
		return false
	}
	for _, s := range allowed {
		if s == to {
			return true
		}
	}
	return false
}
