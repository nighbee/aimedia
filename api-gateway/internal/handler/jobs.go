package handler

import (
	"errors"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/aimedia/api-gateway/internal/model"
	"github.com/aimedia/api-gateway/internal/repository"
	"github.com/aimedia/api-gateway/internal/service"
)

var anonymousInspectorID = uuid.MustParse("00000000-0000-0000-0000-000000000000")

// SubmitJob handles POST /api/v1/jobs (no auth required)
func (h *Handler) SubmitJob(c *fiber.Ctx) error {
	var req model.CreateJobRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid request body"})
	}

	inspectorID, _ := c.Locals("inspector_id").(uuid.UUID)
	if inspectorID == uuid.Nil {
		inspectorID = anonymousInspectorID
	}

	job, err := h.jobService.SubmitJob(c.Context(), req, inspectorID)
	if err != nil {
		h.logger.Warn("job submission failed", zap.Error(err))
		switch {
		case errors.Is(err, service.ErrInvalidURL), errors.Is(err, service.ErrPlatformMismatch),
			errors.Is(err, service.ErrInvalidPriority), errors.Is(err, service.ErrURLTooLong):
			return c.Status(fiber.StatusUnprocessableEntity).JSON(fiber.Map{"error": err.Error()})
		default:
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "failed to submit job"})
		}
	}

	return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
		"job_id":     job.ID.String(),
		"status":     job.Status,
		"created_at": job.CreatedAt,
	})
}

// ListJobs handles GET /api/v1/jobs
func (h *Handler) ListJobs(c *fiber.Ctx) error {
	params := model.ListJobsParams{
		Status: c.Query("status"),
		Page:   c.QueryInt("page", model.DefaultPage),
		Limit:  c.QueryInt("limit", model.DefaultPageSize),
		SortBy: c.Query("sort_by", "risk_score"),
	}

	result, err := h.jobService.ListJobs(c.Context(), params)
	if err != nil {
		h.logger.Error("failed to list jobs", zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "failed to list jobs"})
	}

	return c.JSON(result)
}

// GetJob handles GET /api/v1/jobs/:id
func (h *Handler) GetJob(c *fiber.Ctx) error {
	id, err := uuid.Parse(c.Params("id"))
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid job id"})
	}

	job, result, err := h.jobService.GetJob(c.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "job not found"})
		}
		h.logger.Error("failed to get job", zap.String("job_id", id.String()), zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "failed to get job"})
	}

	resp := fiber.Map{
		"job_id":      job.ID.String(),
		"url":         job.URL,
		"platform":    job.Platform,
		"status":      job.Status,
		"risk_score":  job.RiskScore,
		"confidence":  job.Confidence,
		"reasoning":   job.Reasoning,
		"evidence_url": job.EvidenceURL,
		"created_at":  job.CreatedAt,
		"completed_at": job.CompletedAt,
	}

	if result != nil {
		categories := fiber.Map{}
		if result.IllegalGamblingScore != nil {
			categories["illegal_gambling"] = *result.IllegalGamblingScore
		}
		if result.PyramidSchemeScore != nil {
			categories["pyramid_scheme"] = *result.PyramidSchemeScore
		}
		if result.InvestmentFraudScore != nil {
			categories["investment_fraud"] = *result.InvestmentFraudScore
		}
		if result.ReferralSchemeScore != nil {
			categories["referral_scheme"] = *result.ReferralSchemeScore
		}
		resp["categories"] = categories
		resp["top_flags"] = result.TopFlags
		resp["extracted_signals"] = result.ExtractedSignals
	}

	return c.JSON(resp)
}

// GetEvidence handles GET /api/v1/jobs/:id/evidence
func (h *Handler) GetEvidence(c *fiber.Ctx) error {
	id, err := uuid.Parse(c.Params("id"))
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid job id"})
	}

	evidenceURL, err := h.jobService.GetEvidenceURL(c.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "job not found"})
		}
		h.logger.Error("failed to get evidence url", zap.String("job_id", id.String()), zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "failed to get evidence url"})
	}

	if evidenceURL == nil || *evidenceURL == "" {
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "evidence not available"})
	}

	return c.JSON(fiber.Map{"evidence_url": *evidenceURL})
}
