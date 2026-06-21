package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	Port       string
	Env        string
	GoMaxProcs int

	DB struct {
		Host         string
		Port         string
		User         string
		Password     string
		Name         string
		SSLMode      string
		MaxOpenConns int
		MaxIdleConns int
	}

	Kafka struct {
		Brokers           string
		GroupID           string
		TopicJobCreated   string
		TopicJobCompleted string
	}

	Auth struct {
		JWTSecret     string
		JWTExpiry     time.Duration
		InternalToken string
	}

	S3 struct {
		Endpoint       string
		AccessKey      string
		SecretKey      string
		BucketName     string
		UseSSL         bool
		SignedURLExpiry time.Duration
	}
}

func Load() *Config {
	cfg := &Config{}

	cfg.Port = getEnv("PORT", "8080")
	cfg.Env = getEnv("ENV", "development")
	cfg.GoMaxProcs = getIntEnv("GOMAXPROCS", 1)

	cfg.DB.Host = getEnv("DB_HOST", "localhost")
	cfg.DB.Port = getEnv("DB_PORT", "5432")
	cfg.DB.User = getEnv("DB_USER", "mediawatchuser")
	cfg.DB.Password = getEnv("DB_PASSWORD", "mediawatchpass")
	cfg.DB.Name = getEnv("DB_NAME", "mediawatch")
	cfg.DB.SSLMode = getEnv("DB_SSL_MODE", "disable")
	cfg.DB.MaxOpenConns = getIntEnv("DB_MAX_OPEN_CONNS", 10)
	cfg.DB.MaxIdleConns = getIntEnv("DB_MAX_IDLE_CONNS", 5)

	cfg.Kafka.Brokers = getEnv("KAFKA_BROKERS", "localhost:9092")
	cfg.Kafka.GroupID = getEnv("KAFKA_GROUP_ID", "go-api-consumer")
	cfg.Kafka.TopicJobCreated = getEnv("KAFKA_TOPIC_JOB_CREATED", "media.job.created")
	cfg.Kafka.TopicJobCompleted = getEnv("KAFKA_TOPIC_JOB_COMPLETED", "media.job.completed")

	cfg.Auth.JWTSecret = getEnv("JWT_SECRET", "change-me-in-production")
	cfg.Auth.JWTExpiry = time.Duration(getIntEnv("JWT_EXPIRY_HOURS", 24)) * time.Hour
	cfg.Auth.InternalToken = getEnv("GO_API_INTERNAL_TOKEN", "internal-service-token-change-me")

	// S3 / MinIO (replaces GCS)
	cfg.S3.Endpoint = getEnv("S3_ENDPOINT", "localhost:9000")
	cfg.S3.AccessKey = getEnv("S3_ACCESS_KEY", "minioadmin")
	cfg.S3.SecretKey = getEnv("S3_SECRET_KEY", "minioadminpass")
	cfg.S3.BucketName = getEnv("S3_BUCKET_NAME", "evidence-packs")
	cfg.S3.UseSSL = getEnv("S3_USE_SSL", "false") == "true"
	cfg.S3.SignedURLExpiry = time.Duration(getIntEnv("S3_SIGNED_URL_EXPIRY_HOURS", 168)) * time.Hour

	return cfg
}

func (c *Config) DBDSN() string {
	return "postgres://" + c.DB.User + ":" + c.DB.Password +
		"@" + c.DB.Host + ":" + c.DB.Port +
		"/" + c.DB.Name + "?sslmode=" + c.DB.SSLMode
}

func getEnv(key, fallback string) string {
	if val, ok := os.LookupEnv(key); ok {
		return val
	}
	return fallback
}

func getIntEnv(key string, fallback int) int {
	if val, ok := os.LookupEnv(key); ok {
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return fallback
}
