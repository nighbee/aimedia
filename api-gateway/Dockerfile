# Build stage
FROM golang:1.26-alpine AS builder

RUN apk add --no-cache gcc musl-dev

WORKDIR /app

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o main ./cmd/server

# Execution stage — distroless static (zero shell/packages, ~2MB)
FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app/main /main

EXPOSE 8080

ENTRYPOINT ["/main"]
