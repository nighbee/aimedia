package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"

	"github.com/aimedia/api-gateway/internal/config"
	"github.com/aimedia/api-gateway/internal/model"
	"github.com/aimedia/api-gateway/internal/repository"
)

const (
	maxRetries       = 3
	baseBackoff      = 1 * time.Second
	maxBackoff       = 10 * time.Second
)

type Consumer struct {
	reader  *kafka.Reader
	logger  *zap.Logger
	jobRepo *repository.JobRepository
	resRepo *repository.ResultRepository
	ctx     context.Context
	cancel  context.CancelFunc
}

func NewConsumer(
	cfg *config.Config,
	logger *zap.Logger,
	jobRepo *repository.JobRepository,
	resRepo *repository.ResultRepository,
) *Consumer {
	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     []string{cfg.Kafka.Brokers},
		GroupID:     cfg.Kafka.GroupID,
		Topic:       cfg.Kafka.TopicJobCompleted,
		MinBytes:    1,
		MaxBytes:    10e6,
		MaxWait:     3 * time.Second,
		StartOffset: kafka.LastOffset,
	})
	return &Consumer{reader: r, logger: logger, jobRepo: jobRepo, resRepo: resRepo}
}

func (c *Consumer) Start(ctx context.Context) {
	c.ctx, c.cancel = context.WithCancel(ctx)
	c.logger.Info("starting Kafka consumer",
		zap.String("topic", c.reader.Config().Topic),
		zap.String("group_id", c.reader.Config().GroupID),
	)

	go func() {
		for {
			select {
			case <-c.ctx.Done():
				c.logger.Info("stopping Kafka consumer")
				return
			default:
				msg, err := c.reader.FetchMessage(c.ctx)
				if err != nil {
					if c.ctx.Err() != nil {
						return
					}
					c.logger.Error("kafka fetch error", zap.Error(err))
					time.Sleep(time.Second)
					continue
				}

				processed := c.processMessage(msg)
				if processed {
					if err := c.reader.CommitMessages(c.ctx, msg); err != nil {
						c.logger.Error("failed to commit kafka offset",
							zap.String("key", string(msg.Key)),
							zap.Int64("offset", msg.Offset),
							zap.Int("partition", msg.Partition),
							zap.Error(err),
						)
					}
				}
			}
		}
	}()
}

func (c *Consumer) processMessage(msg kafka.Message) bool {
	logger := c.logger.With(
		zap.String("topic", msg.Topic),
		zap.Int("partition", msg.Partition),
		zap.Int64("offset", msg.Offset),
		zap.String("key", string(msg.Key)),
	)

	var event model.JobCompletedEvent
	if err := json.Unmarshal(msg.Value, &event); err != nil {
		logger.Error("failed to unmarshal job.completed event", zap.Error(err))
		return true // commit offset — can't recover
	}

	logger = logger.With(zap.String("job_id", event.JobID))
	logger.Info("processing job.completed event", zap.String("status", event.Status))

	jobID, err := uuid.Parse(event.JobID)
	if err != nil {
		logger.Error("invalid job_id in event", zap.Error(err))
		return true // commit offset — can't recover
	}

	var processErr error
	switch event.Status {
	case string(model.JobStatusCompleted):
		processErr = c.handleCompleted(logger, jobID, &event)
	case string(model.JobStatusFailed):
		processErr = c.handleFailed(logger, jobID, &event)
	default:
		logger.Warn("unknown job status in completed event", zap.String("status", event.Status))
		return true
	}

	if processErr != nil {
		logger.Error("failed to process event after retries, dropping", zap.Error(processErr))
		return true // commit offset after exhausting retries
	}

	return true
}

func (c *Consumer) handleCompleted(logger *zap.Logger, jobID uuid.UUID, event *model.JobCompletedEvent) error {
	if event.RiskScore == nil {
		return fmt.Errorf("completed event missing risk_score")
	}

	confidence := ""
	if event.Confidence != nil {
		confidence = *event.Confidence
	}
	reasoning := ""
	if event.Reasoning != nil {
		reasoning = *event.Reasoning
	}

	op := func() error {
		return c.jobRepo.Complete(c.ctx, jobID, *event.RiskScore, confidence, reasoning, event.EvidenceURL, event.CustodyLog)
	}
	if err := retryWithBackoff(c.ctx, op, maxRetries, logger); err != nil {
		return fmt.Errorf("complete job: %w", err)
	}

	if event.Categories != nil {
		result := &model.AnalysisResult{JobID: jobID}
		if v, ok := (*event.Categories)["illegal_gambling"]; ok {
			result.IllegalGamblingScore = &v
		}
		if v, ok := (*event.Categories)["pyramid_scheme"]; ok {
			result.PyramidSchemeScore = &v
		}
		if v, ok := (*event.Categories)["investment_fraud"]; ok {
			result.InvestmentFraudScore = &v
		}
		if v, ok := (*event.Categories)["referral_scheme"]; ok {
			result.ReferralSchemeScore = &v
		}
		result.TopFlags = event.TopFlags

		op := func() error {
			return c.resRepo.Upsert(c.ctx, result)
		}
		if err := retryWithBackoff(c.ctx, op, maxRetries, logger); err != nil {
			return fmt.Errorf("upsert result: %w", err)
		}
	}

	logger.Info("job completed successfully", zap.Int("risk_score", *event.RiskScore))
	return nil
}

func (c *Consumer) handleFailed(logger *zap.Logger, jobID uuid.UUID, event *model.JobCompletedEvent) error {
	failedStage := "unknown"
	if event.Error != nil {
		failedStage = *event.Error
	}

	op := func() error {
		return c.jobRepo.UpdateStatus(c.ctx, jobID, model.JobStatusFailed, &failedStage, event.CustodyLog)
	}
	if err := retryWithBackoff(c.ctx, op, maxRetries, logger); err != nil {
		return fmt.Errorf("update job to failed: %w", err)
	}

	logger.Warn("job failed", zap.String("stage", failedStage))
	return nil
}

func (c *Consumer) Close() error {
	if c.cancel != nil {
		c.cancel()
	}
	return c.reader.Close()
}

func retryWithBackoff(ctx context.Context, op func() error, maxRetries int, logger *zap.Logger) error {
	var lastErr error
	backoff := baseBackoff

	for attempt := 0; attempt < maxRetries; attempt++ {
		if attempt > 0 {
			logger.Warn("retrying operation",
				zap.Int("attempt", attempt+1),
				zap.Int("max_retries", maxRetries),
				zap.Duration("backoff", backoff),
				zap.Error(lastErr),
			)

			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
		}

		lastErr = op()
		if lastErr == nil {
			return nil
		}

		backoff = backoff * 2
		if backoff > maxBackoff {
			backoff = maxBackoff
		}
	}

	return fmt.Errorf("all %d retries exhausted: %w", maxRetries, lastErr)
}
