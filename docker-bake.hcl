# Docker Bake — cache-aware parallel builds for all services
# Usage:
#   docker buildx bake          # build all
#   docker buildx bake go-api   # build single service
#   docker buildx bake --print  # preview plan

variable "CACHE_FROM" {
  default = "type=registry,ref=ghcr.io/aimedia/cache:"
}
variable "CACHE_TO" {
  default = "type=inline"
}

group "default" {
  targets = ["go-api", "python-worker", "react-frontend"]
}

target "go-api" {
  dockerfile = "api-gateway/Dockerfile"
  context   = "api-gateway"
  tags      = ["aimedia/go-api:latest"]
  cache-from = ["${CACHE_FROM}go-api"]
  cache-to   = [CACHE_TO]
}

target "python-worker" {
  dockerfile = "media-worker/Dockerfile"
  context   = "media-worker"
  tags      = ["aimedia/python-worker:latest"]
  cache-from = ["${CACHE_FROM}python-worker"]
  cache-to   = [CACHE_TO]
}

target "react-frontend" {
  dockerfile = "frontend/Dockerfile"
  context   = "frontend"
  tags      = ["aimedia/react-frontend:latest"]
  cache-from = ["${CACHE_FROM}react-frontend"]
  cache-to   = [CACHE_TO]
}

target "postgres" {
  image = "postgres:16-alpine"
  tags  = ["aimedia/postgres:latest"]
}

target "kafka" {
  image = "confluentinc/cp-kafka:7.6.0"
  tags  = ["aimedia/kafka:latest"]
}

target "minio" {
  image = "minio/minio:latest"
  tags  = ["aimedia/minio:latest"]
}
