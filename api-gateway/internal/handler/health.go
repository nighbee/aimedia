package handler

import (
	"context"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"
)

func (h *Handler) HealthCheck(c *fiber.Ctx) error {
	components := fiber.Map{
		"api": "running",
	}

	allHealthy := true

	// Check PostgreSQL
	dbCtx, dbCancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer dbCancel()
	if err := h.pool.Ping(dbCtx); err != nil {
		h.logger.Error("health check: db ping failed", zap.Error(err))
		components["database"] = "unreachable"
		allHealthy = false
	} else {
		components["database"] = "connected"
	}

	// Check Kafka connectivity
	conn, err := kafka.DialContext(context.Background(), "tcp", h.kafkaBroker)
	if err != nil {
		h.logger.Error("health check: kafka dial failed", zap.Error(err))
		components["kafka"] = "unreachable"
		allHealthy = false
	} else {
		conn.Close()
		components["kafka"] = "reachable"
	}

	status := fiber.StatusOK
	statusText := "ok"
	if !allHealthy {
		status = fiber.StatusServiceUnavailable
		statusText = "degraded"
	}

	return c.Status(status).JSON(fiber.Map{
		"status":     statusText,
		"components": components,
	})
}
