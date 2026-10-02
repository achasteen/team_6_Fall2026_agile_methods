-- Samaritan Services schema (Neon Postgres).
-- The app applies this on startup (src/db.py), so every statement must be safe to re-run.

CREATE TABLE IF NOT EXISTS users (
    user_id     text PRIMARY KEY,
    password    text NOT NULL,              -- bcrypt hash (legacy plaintext is upgraded on next login)
    role        text NOT NULL DEFAULT 'User' CHECK (role IN ('User', 'Samaritan')),
    first_name  text NOT NULL DEFAULT '',
    last_name   text NOT NULL DEFAULT '',
    city        text NOT NULL DEFAULT '',
    state       text NOT NULL DEFAULT '',
    zip         text NOT NULL DEFAULT '',
    services    text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requests (
    request_id         text PRIMARY KEY,
    request_name       text NOT NULL,
    description        text NOT NULL DEFAULT '',
    zip                text NOT NULL DEFAULT '',
    requested_by_id    text NOT NULL REFERENCES users (user_id),
    requested_by_name  text NOT NULL DEFAULT '',
    status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
    accepted_by_id     text,                -- not a foreign key: some legacy rows point at removed users
    accepted_by_name   text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    accepted_at        timestamptz
);
CREATE INDEX IF NOT EXISTS requests_requested_by_idx ON requests (requested_by_id);
CREATE INDEX IF NOT EXISTS requests_accepted_by_idx ON requests (accepted_by_id);
CREATE INDEX IF NOT EXISTS requests_pending_idx ON requests (status) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS notifications (
    notif_id      text PRIMARY KEY,
    recipient_id  text NOT NULL,
    message       text NOT NULL,
    request_id    text,
    is_read       boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_unread_idx ON notifications (recipient_id) WHERE NOT is_read;

CREATE TABLE IF NOT EXISTS messages (
    message_id    text PRIMARY KEY,
    request_id    text NOT NULL REFERENCES requests (request_id) ON DELETE CASCADE,
    sender_id     text NOT NULL,
    sender_name   text NOT NULL DEFAULT '',
    recipient_id  text NOT NULL,
    body          text NOT NULL,
    sent_at       timestamptz NOT NULL DEFAULT now(),
    read_at       timestamptz                -- set when the recipient opens the conversation
);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at timestamptz;
CREATE INDEX IF NOT EXISTS messages_thread_idx ON messages (request_id, sent_at);
CREATE INDEX IF NOT EXISTS messages_unread_idx ON messages (recipient_id) WHERE read_at IS NULL;
