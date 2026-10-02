"""
One-time copy of the Google Sheets data into Neon Postgres.

Run from the repo root (needs both [connections.gsheets] and [connections.neon]
in .streamlit/secrets.toml):

    python db/migrate_sheets_to_neon.py

Applies db/schema.sql first. Safe to re-run: rows that already exist are skipped.
Google Sheets is only read, never modified.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit_gsheets import GSheetsConnection  # noqa: E402
from src.utils import clean_zip_display  # noqa: E402

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def clean(value):
    """
    Sheet cell -> trimmed string ('' for blanks, no trailing .0 on whole numbers).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text_value = str(value).strip()
    return "" if text_value.lower() == "nan" else text_value


def unguard(value):
    # Undo the formula-injection guard added when values were written to Sheets
    if value.startswith("'") and value[1:2] in FORMULA_TRIGGERS:
        return value[1:]
    return value


def read_sheet(gsheets, name):
    try:
        df = gsheets.read(worksheet=name, ttl=0)
    except Exception as e:
        print(f"  {name}: skipped ({type(e).__name__})")
        return []
    df = df.dropna(how="all")
    df.columns = [str(col).strip() for col in df.columns]
    return [{col: row.get(col) for col in df.columns} for _, row in df.iterrows()]


def ordered_timestamps(count):
    """
    Sheets rows have no timestamps; keep their original order by spacing them a second apart.
    """
    start = datetime.now(timezone.utc) - timedelta(seconds=count + 1)
    return [start + timedelta(seconds=i) for i in range(count)]


def main():
    gsheets = st.connection("gsheets", type=GSheetsConnection)
    engine = create_engine(st.secrets["connections"]["neon"]["url"])

    print("Reading Google Sheets...")
    users = read_sheet(gsheets, "Users")
    requests = read_sheet(gsheets, "Requests")
    notifications = read_sheet(gsheets, "Notifications")
    messages = read_sheet(gsheets, "Messages")

    user_ids = {clean(u.get("user_id")) for u in users} - {""}
    user_by_full_name = {
        f"{clean(u.get('first_name'))} {clean(u.get('last_name'))}".strip(): clean(u.get("user_id"))
        for u in users
    }

    with engine.begin() as conn:
        print("Applying schema...")
        conn.exec_driver_sql((ROOT / "db" / "schema.sql").read_text())

        inserted = 0
        for u in users:
            user_id = clean(u.get("user_id"))
            if not user_id:
                continue
            role = clean(u.get("role")).title()
            inserted += conn.execute(text("""
                INSERT INTO users (user_id, password, role, first_name, last_name, city, state, zip, services)
                VALUES (:user_id, :password, :role, :first_name, :last_name, :city, :state, :zip, :services)
                ON CONFLICT (user_id) DO NOTHING
            """), dict(
                user_id=user_id, password=clean(u.get("password")),
                role=role if role in ("User", "Samaritan") else "User",
                first_name=unguard(clean(u.get("first_name"))), last_name=unguard(clean(u.get("last_name"))),
                city=unguard(clean(u.get("city"))), state=unguard(clean(u.get("state"))),
                zip=clean_zip_display(clean(u.get("zip"))), services=unguard(clean(u.get("services"))),
            )).rowcount
        print(f"  users: {inserted} inserted of {len(users)}")

        inserted, skipped = 0, []
        for r, created_at in zip(requests, ordered_timestamps(len(requests))):
            request_id = clean(r.get("request_id"))
            requester_id = clean(r.get("requested_by_id"))
            if not request_id or requester_id not in user_ids:
                skipped.append(request_id or "(blank id)")
                continue
            status = clean(r.get("status")).lower()
            status = status if status in ("pending", "accepted") else "pending"
            accepted_name = clean(r.get("accepted_by_name")) or clean(r.get("accepted_by"))
            accepted_id = clean(r.get("accepted_by_id")) or user_by_full_name.get(accepted_name, "")
            is_accepted = status == "accepted"
            inserted += conn.execute(text("""
                INSERT INTO requests (request_id, request_name, description, zip, requested_by_id, requested_by_name,
                                      status, accepted_by_id, accepted_by_name, created_at, accepted_at)
                VALUES (:request_id, :request_name, :description, :zip, :requested_by_id, :requested_by_name,
                        :status, :accepted_by_id, :accepted_by_name, :created_at, :accepted_at)
                ON CONFLICT (request_id) DO NOTHING
            """), dict(
                request_id=request_id, request_name=unguard(clean(r.get("request_name"))) or "Request",
                description=unguard(clean(r.get("description"))), zip=clean_zip_display(clean(r.get("zip"))),
                requested_by_id=requester_id,
                requested_by_name=clean(r.get("requested_by_name")) or clean(r.get("requested_by")),
                status=status,
                accepted_by_id=(accepted_id or None) if is_accepted else None,
                accepted_by_name=(accepted_name or None) if is_accepted else None,
                created_at=created_at, accepted_at=created_at if is_accepted else None,
            )).rowcount
        print(f"  requests: {inserted} inserted of {len(requests)}" + (f"; skipped {skipped}" if skipped else ""))

        inserted = 0
        for n, created_at in zip(notifications, ordered_timestamps(len(notifications))):
            notif_id = clean(n.get("notif_id"))
            if not notif_id:
                continue
            inserted += conn.execute(text("""
                INSERT INTO notifications (notif_id, recipient_id, message, request_id, is_read, created_at)
                VALUES (:notif_id, :recipient_id, :message, :request_id, :is_read, :created_at)
                ON CONFLICT (notif_id) DO NOTHING
            """), dict(
                notif_id=notif_id, recipient_id=clean(n.get("recipient_id")), message=clean(n.get("message")),
                request_id=clean(n.get("request_id")) or None,
                is_read=clean(n.get("is_read")).upper() in ("TRUE", "1", "YES", "READ"),
                created_at=created_at,
            )).rowcount
        print(f"  notifications: {inserted} inserted of {len(notifications)}")

        known_requests = set(conn.execute(text("SELECT request_id FROM requests")).scalars())
        inserted, skipped = 0, []
        for m, fallback_time in zip(messages, ordered_timestamps(len(messages))):
            message_id, request_id = clean(m.get("message_id")), clean(m.get("request_id"))
            if not message_id or request_id not in known_requests:
                skipped.append(message_id or "(blank id)")
                continue
            try:
                sent_at = datetime.fromisoformat(clean(m.get("sent_at")))
            except ValueError:
                sent_at = fallback_time
            inserted += conn.execute(text("""
                INSERT INTO messages (message_id, request_id, sender_id, sender_name, recipient_id, body, sent_at)
                VALUES (:message_id, :request_id, :sender_id, :sender_name, :recipient_id, :body, :sent_at)
                ON CONFLICT (message_id) DO NOTHING
            """), dict(
                message_id=message_id, request_id=request_id, sender_id=clean(m.get("sender_id")),
                sender_name=clean(m.get("sender_name")), recipient_id=clean(m.get("recipient_id")),
                body=unguard(clean(m.get("body"))), sent_at=sent_at,
            )).rowcount
        print(f"  messages: {inserted} inserted of {len(messages)}" + (f"; skipped {skipped}" if skipped else ""))

    print("Done.")


if __name__ == "__main__":
    main()
