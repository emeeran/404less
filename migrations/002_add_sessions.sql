-- Migration: 002_add_sessions
-- @spec FEAT-002/DM-001 (Session)
-- @spec FEAT-002/DM-002 (LoginAttempt)
-- Created: 2024-01-12

-- Sessions table
-- @spec FEAT-002/DM-001
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT sessions_refresh_token_unique UNIQUE (refresh_token_hash)
);

-- Login attempts table (for rate limiting and lockout)
-- @spec FEAT-002/DM-002
CREATE TABLE login_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    ip_address INET,
    success BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_revoked_at ON sessions(revoked_at) WHERE revoked_at IS NULL;
CREATE INDEX idx_login_attempts_email ON login_attempts(email);
CREATE INDEX idx_login_attempts_created_at ON login_attempts(created_at);

-- Comments
COMMENT ON TABLE sessions IS '@spec FEAT-002/DM-001 - User sessions';
COMMENT ON TABLE login_attempts IS '@spec FEAT-002/DM-002 - Login attempt history';
