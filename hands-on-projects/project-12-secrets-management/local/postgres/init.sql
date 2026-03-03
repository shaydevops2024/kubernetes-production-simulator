-- PostgreSQL initialization script
-- Creates the application database structure.
-- Vault will manage user creation/deletion dynamically.

-- Application tables
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id         SERIAL PRIMARY KEY,
    user_id    INT REFERENCES users(id),
    amount     DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id         SERIAL PRIMARY KEY,
    event_type VARCHAR(100),
    details    TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed data so dynamic credentials have something to query
INSERT INTO users (email) VALUES
    ('alice@example.com'),
    ('bob@example.com'),
    ('carol@example.com')
ON CONFLICT DO NOTHING;

INSERT INTO orders (user_id, amount) VALUES
    (1, 99.99),
    (1, 149.00),
    (2, 49.99)
ON CONFLICT DO NOTHING;

-- Grant privileges on existing tables to vault_admin
-- (Vault will grant subset of these to dynamically created users)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vault_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vault_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO vault_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO vault_admin;
