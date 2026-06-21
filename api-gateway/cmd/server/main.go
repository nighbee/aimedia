package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"runtime"
	"sync"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/aimedia/api-gateway/internal/config"
	"github.com/aimedia/api-gateway/internal/handler"
	"github.com/aimedia/api-gateway/internal/queue"
	"github.com/aimedia/api-gateway/internal/repository"
	"github.com/aimedia/api-gateway/internal/router"
	"github.com/aimedia/api-gateway/internal/service"
	"github.com/aimedia/api-gateway/internal/storage"
)

func main() {
	cfg := config.Load()

	// Set GOMAXPROCS
	runtime.GOMAXPROCS(cfg.GoMaxProcs)

	// Initialize logger
	logger := initLogger(cfg)
	defer logger.Sync()

	logger.Info("starting API Gateway",
		zap.String("env", cfg.Env),
		zap.String("port", cfg.Port),
		zap.Int("gomaxprocs", cfg.GoMaxProcs),
	)

	// Connect to PostgreSQL
	pool, err := initDB(cfg)
	if err != nil {
		logger.Fatal("failed to connect to database", zap.Error(err))
	}
	defer pool.Close()
	logger.Info("connected to PostgreSQL")

	// Initialize repositories
	jobRepo := repository.NewJobRepository(pool)
	resRepo := repository.NewResultRepository(pool)
	userRepo := repository.NewUserRepository(pool)

	// Initialize Kafka producer
	producer := queue.NewProducer(cfg, logger)
	defer producer.Close()
	logger.Info("Kafka producer initialized")

	// Initialize Kafka consumer
	consumer := queue.NewConsumer(cfg, logger, jobRepo, resRepo)
	defer consumer.Close()

	// WaitGroup to track consumer goroutine lifetime
	var wg sync.WaitGroup

	// Initialize S3 client (MinIO — optional, won't block startup if unavailable)
	s3Client, err := storage.NewS3Client(cfg, logger)
	if err != nil {
		logger.Warn("S3 client not available, evidence signing disabled", zap.Error(err))
	} else {
		defer s3Client.Close()
		logger.Info("S3 client initialized",
			zap.String("endpoint", cfg.S3.Endpoint),
			zap.String("bucket", cfg.S3.BucketName),
		)
	}

	// Initialize service layer
	jobService := service.NewJobService(jobRepo, resRepo, producer, logger)
	if s3Client != nil {
		jobService.SetS3Client(s3Client)
	}

	// Initialize handlers
	h := handler.New(jobService, logger, pool, cfg.Kafka.Brokers)
	authHandler := handler.NewAuthHandler(userRepo, cfg, logger)

	// Setup Fiber app with body size limit (1MB default, 5MB for evidence uploads)
	app := fiber.New(fiber.Config{
		ReadTimeout:     10 * time.Second,
		WriteTimeout:    15 * time.Second,
		IdleTimeout:     60 * time.Second,
		BodyLimit:       5 * 1024 * 1024, // 5MB
		ReadBufferSize:  4096,
	})

	router.Setup(app, h, authHandler, cfg, logger)

	// Graceful shutdown
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		logger.Info("shutting down server...")
		app.Shutdown()
	}()

	// Start server first, then consumer (readiness gate)
	addr := ":" + cfg.Port
	logger.Info("HTTP server listening", zap.String("addr", addr))

	// Start the consumer after the server is listening
	wg.Add(1)
	go func() {
		defer wg.Done()
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()

		// Brief delay to ensure HTTP listener is ready
		time.Sleep(500 * time.Millisecond)
		consumer.Start(ctx)
		logger.Info("Kafka consumer started")

		// Block until shutdown signal
		<-ctx.Done()
	}()

	if err := app.Listen(addr); err != nil {
		logger.Fatal("server error", zap.Error(err))
	}

	// Wait for consumer to finish
	wg.Wait()
	logger.Info("server stopped")
}

func initLogger(cfg *config.Config) *zap.Logger {
	var level zapcore.Level
	if cfg.Env == "production" {
		level = zapcore.InfoLevel
	} else {
		level = zapcore.DebugLevel
	}

	encoderCfg := zap.NewProductionEncoderConfig()
	encoderCfg.TimeKey = "timestamp"
	encoderCfg.EncodeTime = zapcore.ISO8601TimeEncoder

	logger, err := zap.Config{
		Level:            zap.NewAtomicLevelAt(level),
		Development:      cfg.Env != "production",
		Encoding:         "json",
		EncoderConfig:    encoderCfg,
		OutputPaths:      []string{"stdout"},
		ErrorOutputPaths: []string{"stderr"},
	}.Build()

	if err != nil {
		log.Fatalf("failed to initialize logger: %v", err)
	}

	return logger
}

func initDB(cfg *config.Config) (*pgxpool.Pool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	poolCfg, err := pgxpool.ParseConfig(cfg.DBDSN())
	if err != nil {
		return nil, err
	}

	poolCfg.MaxConns = int32(cfg.DB.MaxOpenConns)
	poolCfg.MinConns = int32(cfg.DB.MaxIdleConns)

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, err
	}

	// Verify DB connectivity
	pingCtx, pingCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer pingCancel()
	if err := pool.Ping(pingCtx); err != nil {
		pool.Close()
		return nil, err
	}

	return pool, nil
}
