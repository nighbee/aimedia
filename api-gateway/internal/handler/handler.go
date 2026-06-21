package handler

import (
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/aimedia/api-gateway/internal/service"
	"go.uber.org/zap"
)

type Handler struct {
	jobService service.JobService
	logger     *zap.Logger
	pool       *pgxpool.Pool
	kafkaBroker string
}

func New(jobService service.JobService, logger *zap.Logger, pool *pgxpool.Pool, kafkaBroker string) *Handler {
	return &Handler{
		jobService:  jobService,
		logger:      logger,
		pool:        pool,
		kafkaBroker: kafkaBroker,
	}
}
