package model

type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type LoginResponse struct {
	Token       string `json:"token"`
	InspectorID string `json:"inspector_id"`
	Email       string `json:"email"`
	Role        string `json:"role"`
}

type User struct {
	ID           string `db:"id"`
	Email        string `db:"email"`
	PasswordHash string `db:"password_hash"`
	Role         string `db:"role"`
}
