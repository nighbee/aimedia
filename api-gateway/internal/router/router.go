package router

import (
	"github.com/gofiber/fiber/v2"

	"github.com/aimedia/api-gateway/internal/config"
	"github.com/aimedia/api-gateway/internal/handler"
	"github.com/aimedia/api-gateway/internal/middleware"
	"go.uber.org/zap"
)

func Setup(app *fiber.App, h *handler.Handler, authHandler *handler.AuthHandler, cfg *config.Config, logger *zap.Logger) {
	// Global middleware — order matters
	app.Use(middleware.CORS())
	app.Use(middleware.RequestID())
	app.Use(middleware.Recovery(logger))
	app.Use(middleware.Logger(logger))
	app.Use(middleware.RateLimit())

	// Health — no auth required
	app.Get("/api/v1/health", h.HealthCheck)

	// Auth — no auth required
	app.Post("/api/v1/auth/login", authHandler.Login)

	// Job submission + status polling — no auth required
	app.Post("/api/v1/jobs", h.SubmitJob)
	app.Get("/api/v1/jobs/:id", h.GetJob)
	app.Get("/api/v1/jobs", h.ListJobs)

	// External API — JWT protected
	api := app.Group("/api/v1", middleware.JWTAuth(cfg, logger))
	api.Get("/jobs/:id/evidence", h.GetEvidence)

	// Internal API — internal token protected (called by Python worker)
	internal := app.Group("/internal/v1", middleware.InternalToken(cfg, logger))
	internal.Patch("/jobs/:id/status", h.UpdateJobStatus)
	internal.Patch("/jobs/:id/evidence", h.UpdateEvidenceURL)
}
