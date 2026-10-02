"""
Data access for the Neon Postgres database.

Every read and write the app makes goes through this module. The connection
URL comes from .streamlit/secrets.toml:

    [connections.neon]
    url = "postgresql+psycopg://..."
"""
import streamlit as st
from sqlalchemy import text

import src.utils as utils


def _engine():
    # pool_pre_ping reconnects transparently after Neon suspends an idle database
    return st.connection("neon", type="sql", pool_pre_ping=True, pool_recycle=300).engine


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
def thread_messages(request_id):
    return _query(
        "SELECT * FROM messages WHERE request_id = :request_id ORDER BY sent_at, message_id",
        request_id=request_id,
    )


def message_counts(request_ids):
    """
    Returns {request_id: number of messages} for the given requests.
    """
    if not request_ids:
        return {}
    rows = _query("""
        SELECT request_id, count(*) AS n FROM messages
        WHERE request_id = ANY(:request_ids)
        GROUP BY request_id
    """, request_ids=list(request_ids))
    return {row["request_id"]: row["n"] for row in rows}


def send_message(request_id, sender_id, sender_name, recipient_id, body, notification, notification_prefix):
    """
    Saves a message and notifies the recipient, unless they already have an unread
    notification for this thread starting with notification_prefix. One transaction.
    """
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO messages (message_id, request_id, sender_id, sender_name, recipient_id, body)
            VALUES (:message_id, :request_id, :sender_id, :sender_name, :recipient_id, :body)
        """), dict(message_id=utils.generate_secure_id("msg"), request_id=request_id,
                   sender_id=sender_id, sender_name=sender_name, recipient_id=recipient_id, body=body))

        already_notified = conn.execute(text("""
            SELECT 1 FROM notifications
            WHERE recipient_id = :recipient_id AND request_id = :request_id
              AND NOT is_read AND starts_with(message, :prefix)
            LIMIT 1
        """), dict(recipient_id=recipient_id, request_id=request_id, prefix=notification_prefix)).first()
        if not already_notified:
            _insert_notification(conn, recipient_id, notification, request_id)
