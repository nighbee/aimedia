package queue

import (
	"context"
	"encoding/json"
	"time"

	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"

	"github.com/aimedia/api-gateway/internal/config"
)

type Producer struct {
	writer *kafka.Writer
	logger *zap.Logger
}

func NewProducer(cfg *config.Config, logger *zap.Logger) *Producer {
	w := &kafka.Writer{
		Addr:                   kafka.TCP(cfg.Kafka.Brokers),
		Topic:                  cfg.Kafka.TopicJobCreated,
		Balancer:               &kafka.Hash{},
		WriteTimeout:           10 * time.Second,
		RequiredAcks:           kafka.RequireOne,
		AllowAutoTopicCreation: true,
	}
	return &Producer{writer: w, logger: logger}
}

type JobCreatedMessage struct {
	JobID       string    `json:"job_id"`
	URL         string    `json:"url"`
	Platform    string    `json:"platform"`
	Priority    int       `json:"priority"`
	InspectorID string    `json:"inspector_id"`
	SubmittedAt time.Time `json:"submitted_at"`
}

func (p *Producer) PublishJobCreated(ctx context.Context, jobID, url, platform, inspectorID string, priority int) error {
	msg := JobCreatedMessage{
		JobID:       jobID,
		URL:         url,
		Platform:    platform,
		Priority:    priority,
		InspectorID: inspectorID,
		SubmittedAt: time.Now().UTC(),
	}
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}

	err = p.writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(jobID),
		Value: data,
	})
	if err != nil {
		p.logger.Error("failed to publish job.created event", zap.String("job_id", jobID), zap.Error(err))
		return err
	}

	p.logger.Info("published job.created event", zap.String("job_id", jobID), zap.String("topic", p.writer.Topic))
	return nil
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
