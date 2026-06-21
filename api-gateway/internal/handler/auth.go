package handler

import (
	"errors"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"go.uber.org/zap"
	"golang.org/x/crypto/bcrypt"

	"github.com/aimedia/api-gateway/internal/config"
	"github.com/aimedia/api-gateway/internal/model"
	"github.com/aimedia/api-gateway/internal/repository"
)

type AuthHandler struct {
	userRepo *repository.UserRepository
	cfg      *config.Config
	logger   *zap.Logger
}

func NewAuthHandler(userRepo *repository.UserRepository, cfg *config.Config, logger *zap.Logger) *AuthHandler {
	return &AuthHandler{userRepo: userRepo, cfg: cfg, logger: logger}
}

func (h *AuthHandler) Login(c *fiber.Ctx) error {
	var req model.LoginRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid request body"})
	}

	if req.Email == "" || req.Password == "" {
		return c.Status(fiber.StatusUnprocessableEntity).JSON(fiber.Map{"error": "email and password are required"})
	}

	user, err := h.userRepo.FindByEmail(c.Context(), req.Email)
	if err != nil {
		if errors.Is(err, repository.ErrUserNotFound) {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{"error": "invalid email or password"})
		}
		h.logger.Error("failed to lookup user", zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "authentication failed"})
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
		return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{"error": "invalid email or password"})
	}

	inspectorID, err := uuid.Parse(user.ID)
	if err != nil {
		h.logger.Error("invalid user ID in database", zap.String("user_id", user.ID), zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "authentication failed"})
	}

	now := time.Now()
	claims := jwt.MapClaims{
		"inspector_id": inspectorID.String(),
		"email":        user.Email,
		"role":         user.Role,
		"iat":          now.Unix(),
		"exp":          now.Add(h.cfg.Auth.JWTExpiry).Unix(),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenStr, err := token.SignedString([]byte(h.cfg.Auth.JWTSecret))
	if err != nil {
		h.logger.Error("failed to sign JWT", zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "authentication failed"})
	}

	h.logger.Info("user logged in",
		zap.String("email", user.Email),
		zap.String("role", user.Role),
	)

	return c.JSON(model.LoginResponse{
		Token:       tokenStr,
		InspectorID: inspectorID.String(),
		Email:       user.Email,
		Role:        user.Role,
	})
}
