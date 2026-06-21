package storage

import (
	"context"
	"fmt"
	"net/url"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"go.uber.org/zap"

	"github.com/aimedia/api-gateway/internal/config"
)

// S3Client wraps minio-go to provide presigned URL generation
// for evidence pack PDFs stored in MinIO (or any S3-compatible service).
type S3Client struct {
	client    *minio.Client
	bucket    string
	expiry    time.Duration
	endpoint  string
	useSSL    bool
	logger    *zap.Logger
}

func NewS3Client(cfg *config.Config, logger *zap.Logger) (*S3Client, error) {
	useSSL := cfg.S3.UseSSL

	client, err := minio.New(cfg.S3.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.S3.AccessKey, cfg.S3.SecretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create S3 client: %w", err)
	}

	return &S3Client{
		client:   client,
		bucket:   cfg.S3.BucketName,
		expiry:   cfg.S3.SignedURLExpiry,
		endpoint: cfg.S3.Endpoint,
		useSSL:   useSSL,
		logger:   logger,
	}, nil
}

// PresignedURL generates a presigned GET URL for the given object path.
// If the object path is empty, returns nil without error.
func (s *S3Client) PresignedURL(ctx context.Context, objectPath string) (*string, error) {
	if objectPath == "" {
		return nil, nil
	}

	u, err := s.client.PresignedGetObject(ctx, s.bucket, objectPath, s.expiry, url.Values{})
	if err != nil {
		s.logger.Error("failed to generate presigned URL",
			zap.String("bucket", s.bucket),
			zap.String("object", objectPath),
			zap.Error(err),
		)
		return nil, fmt.Errorf("failed to generate presigned URL: %w", err)
	}

	urlStr := u.String()
	return &urlStr, nil
}

func (s *S3Client) Close() error {
	return nil
}
