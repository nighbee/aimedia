CREATE TABLE core.users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          VARCHAR(32) NOT NULL DEFAULT 'inspector',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed a default admin inspector for hackathon demo
-- Password: admin123 (bcrypt hash)
INSERT INTO core.users (id, email, password_hash, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin@mediawatch.ai',
    '$2b$10$COYzYionF2AfieUQiavkKeBG0tHmq3qYIlN.Krs1uVpPCI4U.h/Dy',
    'admin'
)
ON CONFLICT (id) DO NOTHING;
