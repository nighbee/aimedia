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

// UpdateJobStatus handles PATCH /internal/v1/jobs/:id/status
// Called by the Python worker to update job processing state.
func (h *Handler) UpdateJobStatus(c *fiber.Ctx) error {
	id, err := uuid.Parse(c.Params("id"))
	if err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid job id"})
	}

	var req model.UpdateStatusRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid request body"})
	}

	status := model.JobStatus(req.Status)
	switch status {
	case model.JobStatusDownloading, model.JobStatusExtracting,
		model.JobStatusAnalyzing, model.JobStatusAggregating,
		model.JobStatusGeneratingEvidence:
		// valid intermediate status
	default:
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid status"})
	}

	if err := h.jobService.UpdateJobStatus(c.Context(), id, status); err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "job not found"})
		}
		if errors.Is(err, service.ErrInvalidTransition) {
			return c.Status(fiber.StatusConflict).JSON(fiber.Map{"error": err.Error()})
		}
		h.logger.Error("failed to update job status", zap.String("job_id", id.String()), zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "failed to update status"})
	}

	h.logger.Info("job status updated",
		zap.String("job_id", id.String()),
		zap.String("status", string(status)),
	)

	return c.JSON(fiber.Map{"status": status})
}
