"""
Data access for the Neon Postgres database.

Every read and write the app makes goes through this module. The connection
URL comes from .streamlit/secrets.toml:

    [connections.neon]
    url = "postgresql+psycopg://..."
"""
from pathlib import Path

import streamlit as st
from sqlalchemy import text

import src.utils as utils


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


@st.cache_resource
def _ensure_schema(_db_engine):
    # Runs once per server process; schema.sql is idempotent, so a fresh database sets itself up.
    # (The leading underscore tells Streamlit not to hash the engine argument.)
    with _db_engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_PATH.read_text())
    return True


def _engine():
    # pool_pre_ping reconnects transparently after Neon suspends an idle database
    engine = st.connection("neon", type="sql", pool_pre_ping=True, pool_recycle=300).engine
    _ensure_schema(engine)
    return engine


def _rows(conn, sql, **params):
    return [dict(row._mapping) for row in conn.execute(text(sql), params)]


def _query(sql, **params):
    with _engine().connect() as conn:
        return _rows(conn, sql, **params)


def _query_one(sql, **params):
    rows = _query(sql, **params)
    return rows[0] if rows else None


def _insert_notification(conn, recipient_id, message, request_id=None):
    conn.execute(
        text("""
            INSERT INTO notifications (notif_id, recipient_id, message, request_id)
            VALUES (:notif_id, :recipient_id, :message, :request_id)
        """),
        dict(notif_id=utils.generate_secure_id("notif"), recipient_id=recipient_id,
             message=message, request_id=request_id),
    )


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------
def get_user(user_id):
    return _query_one("SELECT * FROM users WHERE user_id = :user_id", user_id=user_id)


def create_user(user_id, password_hash, role, first_name, last_name, city, state, zip_code, services):
    """
    Returns False if the User ID is already taken.
    """
    with _engine().begin() as conn:
        created = _rows(conn, """
            INSERT INTO users (user_id, password, role, first_name, last_name, city, state, zip, services)
            VALUES (:user_id, :password, :role, :first_name, :last_name, :city, :state, :zip, :services)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING user_id
        """, user_id=user_id, password=password_hash, role=role, first_name=first_name,
            last_name=last_name, city=city, state=state, zip=zip_code, services=services)
    return bool(created)


def set_password_hash(user_id, password_hash):
    with _engine().begin() as conn:
        conn.execute(text("UPDATE users SET password = :password WHERE user_id = :user_id"),
                     dict(password=password_hash, user_id=user_id))


# ---------------------------------------------------------
# REQUESTS
# ---------------------------------------------------------
def create_request(name, description, zip_code, requester_id, requester_name):
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO requests (request_id, request_name, description, zip, requested_by_id, requested_by_name)
            VALUES (:request_id, :name, :description, :zip, :requester_id, :requester_name)
        """), dict(request_id=utils.generate_secure_id(), name=name, description=description,
                   zip=zip_code, requester_id=requester_id, requester_name=requester_name))

def get_request_for_user(request_id, user_id):
    return _query_one("""
        SELECT *
        FROM requests
        WHERE request_id = :request_id
          AND status = 'accepted'
          AND (
              requested_by_id = :user_id
              OR accepted_by_id = :user_id
          )
    """, request_id=request_id, user_id=user_id)

def get_request(request_id):
    return _query_one("SELECT * FROM requests WHERE request_id = :request_id", request_id=request_id)


def requests_by_requester(user_id):
    return _query(
        "SELECT * FROM requests WHERE requested_by_id = :user_id ORDER BY created_at DESC",
        user_id=user_id,
    )


def pending_requests():
    return _query("SELECT * FROM requests WHERE status = 'pending' ORDER BY created_at DESC")


def requests_accepted_by(user_id):
    return _query("""
        SELECT * FROM requests
        WHERE status = 'accepted' AND accepted_by_id = :user_id
        ORDER BY accepted_at DESC NULLS LAST, created_at DESC
    """, user_id=user_id)


def accept_request(request_id, samaritan_id, samaritan_name):
    """
    Accepts a request only if it's still pending, and notifies the requester in the
    same transaction. Returns the updated request, or None if someone else got it first.
    """
    with _engine().begin() as conn:
        rows = _rows(conn, """
            UPDATE requests
            SET status = 'accepted', accepted_by_id = :samaritan_id,
                accepted_by_name = :samaritan_name, accepted_at = now()
            WHERE request_id = :request_id AND status = 'pending'
            RETURNING *
        """, request_id=request_id, samaritan_id=samaritan_id, samaritan_name=samaritan_name)
        if not rows:
            return None
        accepted = rows[0]
        _insert_notification(
            conn, accepted["requested_by_id"],
            f"{samaritan_name} accepted your request '{accepted['request_name']}'.", request_id,
        )
    return accepted


# ---------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------
def unread_notifications(user_id):
    return _query("""
        SELECT * FROM notifications
        WHERE recipient_id = :user_id AND NOT is_read
        ORDER BY created_at
    """, user_id=user_id)


def mark_notification_read(notif_id, user_id):
    with _engine().begin() as conn:
        conn.execute(text("""
            UPDATE notifications SET is_read = true
            WHERE notif_id = :notif_id AND recipient_id = :user_id
        """), dict(notif_id=notif_id, user_id=user_id))


# ---------------------------------------------------------
# MESSAGES
# ---------------------------------------------------------
def conversations(user_id):
    """
    One row per conversation the user is part of (an accepted request with at least one
    message), newest first, with the other person, the latest message and how many
    messages the user hasn't read.
    """
    return _query("""
        SELECT r.request_id, r.request_name,
               CASE WHEN r.requested_by_id = :user_id THEN r.accepted_by_id ELSE r.requested_by_id END AS partner_id,
               CASE WHEN r.requested_by_id = :user_id THEN r.accepted_by_name ELSE r.requested_by_name END AS partner_name,
               last.body AS last_body, last.sender_id AS last_sender_id, last.sent_at AS last_sent_at,
               (SELECT count(*) FROM messages m
                WHERE m.request_id = r.request_id AND m.recipient_id = :user_id AND m.read_at IS NULL) AS unread
        FROM requests r
        JOIN LATERAL (
            SELECT body, sender_id, sent_at FROM messages m
            WHERE m.request_id = r.request_id
            ORDER BY sent_at DESC, message_id DESC
            LIMIT 1
        ) last ON true
        WHERE r.status = 'accepted' AND (r.requested_by_id = :user_id OR r.accepted_by_id = :user_id)
        ORDER BY last.sent_at DESC
    """, user_id=user_id)


def unread_message_count(user_id, except_request_id=None):
    return _query_one("""
        SELECT count(*) AS n FROM messages
        WHERE recipient_id = :user_id AND read_at IS NULL
          AND request_id IS DISTINCT FROM :except_request_id
    """, user_id=user_id, except_request_id=except_request_id)["n"]


def thread_messages(request_id):
    return _query(
        "SELECT * FROM messages WHERE request_id = :request_id ORDER BY sent_at, message_id",
        request_id=request_id,
    )

def thread_messages_for_user(request_id, user_id):
    return _query("""
        SELECT m.*
        FROM messages m
        JOIN requests r ON r.request_id = m.request_id
        WHERE m.request_id = :request_id
          AND r.status = 'accepted'
          AND (
              r.requested_by_id = :user_id
              OR r.accepted_by_id = :user_id
          )
        ORDER BY m.sent_at, m.message_id
    """, request_id=request_id, user_id=user_id)

def mark_thread_read(request_id, user_id):
    with _engine().begin() as conn:
        conn.execute(text("""
            UPDATE messages m
            SET read_at = now()
            FROM requests r
            WHERE m.request_id = :request_id
              AND m.request_id = r.request_id
              AND m.recipient_id = :user_id
              AND r.status = 'accepted'
              AND (r.requested_by_id = :user_id OR r.accepted_by_id = :user_id)
              AND m.read_at IS NULL
        """), dict(request_id=request_id, user_id=user_id))


def send_message(request_id, sender_id, sender_name, recipient_id, body):
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO messages (message_id, request_id, sender_id, sender_name, recipient_id, body)
            SELECT :message_id, :request_id, :sender_id, :sender_name, :recipient_id, :body
            WHERE EXISTS (
                SELECT 1
                FROM requests r
                WHERE r.request_id = :request_id
                  AND r.status = 'accepted'
                  AND (
                      r.requested_by_id = :sender_id
                      OR r.accepted_by_id = :sender_id
                  )
                  AND r.requested_by_id = :recipient_id
                  OR r.accepted_by_id = :recipient_id
            )
        """), dict(message_id=utils.generate_secure_id("msg"), request_id=request_id,
                   sender_id=sender_id, sender_name=sender_name, recipient_id=recipient_id, body=body))
