import streamlit as st
import pandas as pd
import numpy as np
import uuid
import hmac
import bcrypt
from datetime import datetime

import src.ui as ui

# bcrypt only uses the first 72 bytes of input; longer passwords are rejected
BCRYPT_MAX_BYTES = 72
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

def hash_password(plain_password):
    """
    Hashes a plaintext password with bcrypt (salted). Returns the hash as a string.
    """
    return bcrypt.hashpw(str(plain_password).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def is_bcrypt_hash(value):
    """
    Returns True if the value looks like a bcrypt hash.
    """
    return isinstance(value, str) and value.startswith(BCRYPT_PREFIXES)

def verify_password(plain_password, stored_value):
    """
    Checks a plaintext password against the stored value.
    Supports legacy plaintext records so they can be migrated on next login.
    Returns (is_valid, needs_rehash).
    """
    if pd.isna(stored_value):
        return False, False
    stored = str(stored_value).strip()
    candidate = str(plain_password).encode("utf-8")

    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(candidate, stored.encode("utf-8")), False
        except ValueError:
            return False, False

    # Legacy plaintext record: constant-time comparison, flag for upgrade
    if not stored:
        return False, False
    is_valid = hmac.compare_digest(candidate, stored.encode("utf-8"))
    return is_valid, is_valid

def generate_secure_id(prefix=""):
    """
    Generates a unique short ID string.
    """
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{unique_id}" if prefix else unique_id

def clean_zip_display(zip_val):
    """
    Cleans and formats zip codes to 5-digit strings.
    """
    if pd.isna(zip_val) or not zip_val:
        return ""
    try:
        val_str = str(zip_val).split('.')[0].strip()
        return val_str.zfill(5)
    except Exception:
        return str(zip_val)

def fetch_worksheet_cached(conn, worksheet_name, ttl=5):
    """
    Fetches worksheet data with 5s caching to prevent hitting 
    Google Sheets API 60 req/min rate limits.
    """
    return conn.read(worksheet=worksheet_name, ttl=ttl)

def sanitize_for_csv(value):
    formula_triggers = ("=", "+", "-", "@", "\t", "\r")
    if isinstance(value, str) and value.startswith(formula_triggers):
        return "'" + value
    return value

def safe_update_worksheet(conn, worksheet_name, df):
    """
    Cleans out any NaN/inf values before updating Google Sheets to avoid
    JSON compliance errors, then clears Streamlit's cache.
    """
    clean_df = df.copy()
    clean_df = clean_df.replace([np.inf, -np.inf], np.nan).fillna("")
    clean_df = clean_df.apply(lambda col: col.map(sanitize_for_csv))

    conn.update(worksheet=worksheet_name, data=clean_df)
    st.cache_data.clear()

def _gspread_worksheet(conn, worksheet_name, columns):
    """
    Returns the underlying gspread worksheet, creating it with a header row if it doesn't exist.
    Returns None when the connection doesn't expose a gspread client.
    """
    client = getattr(conn, "client", None)
    if not hasattr(client, "_select_worksheet"):
        return None

    import gspread
    try:
        return client._select_worksheet(worksheet=worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = client._open_spreadsheet().add_worksheet(title=worksheet_name, rows=1, cols=len(columns))
        worksheet.append_row(columns, value_input_option="RAW")
        return worksheet

def append_row(conn, worksheet_name, row, columns):
    """
    Appends one row without rewriting the sheet, so concurrent writers can't
    overwrite each other. Falls back to a read + full update if needed.
    """
    values = [sanitize_for_csv("" if pd.isna(row.get(col)) else str(row.get(col))) for col in columns]

    worksheet = _gspread_worksheet(conn, worksheet_name, columns)
    if worksheet is not None:
        worksheet.append_row(values, value_input_option="RAW", table_range="A1")
        st.cache_data.clear()
        return

    try:
        existing_df = fetch_worksheet_cached(conn, worksheet_name, ttl=0)
    except Exception:
        existing_df = pd.DataFrame(columns=columns)
    updated_df = pd.concat([existing_df, pd.DataFrame([dict(zip(columns, values))])], ignore_index=True)
    safe_update_worksheet(conn, worksheet_name, updated_df)

def handle_db_error(e, fallback_msg):
    """
    Renders user-friendly error messages for database and rate-limit errors.
    """
    err_str = str(e)
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "RATE_LIMIT_EXHAUSTED" in err_str:
        st.warning("The database is busy right now. Wait a few seconds and try again.", icon=":material/hourglass_top:")
    else:
        st.error(f"{fallback_msg} Please try again in a moment.")
        st.caption(f"Details: {err_str[:120]}...")  # Truncates long raw traces

def render_dob_selector(key_prefix="dob"):
    """
    Renders standard dropdowns for Date of Birth selection (Month, Day, Year).
    """
    col_m, col_d, col_y = st.columns(3)
    
    months = [
        "January", "February", "March", "April", "May", "June", 
        "July", "August", "September", "October", "November", "December"
    ]
    current_year = datetime.now().year
    years = list(range(current_year - 100, current_year + 1))[::-1]
    
    with col_m:
        month = st.selectbox("Month", options=months, key=f"{key_prefix}_month")
    with col_d:
        day = st.selectbox("Day", options=list(range(1, 32)), key=f"{key_prefix}_day")
    with col_y:
        year = st.selectbox("Year", options=years, key=f"{key_prefix}_year")

    month_num = months.index(month) + 1
    return f"{year:04d}-{month_num:02d}-{day:02d}"

def create_notification(conn, recipient_id, message, request_id=""):
    """
    Creates a new notification entry and appends it to the Notifications worksheet.
    """
    try:
        notif_df = fetch_worksheet_cached(conn, "Notifications", ttl=0)
    except Exception:
        notif_df = pd.DataFrame(columns=["notif_id", "recipient_id", "message", "request_id", "is_read"])

    new_notif = pd.DataFrame([{
        "notif_id": generate_secure_id("notif"),
        "recipient_id": str(recipient_id).strip(),
        "message": str(message),
        "request_id": str(request_id),
        "is_read": "FALSE"
    }])

    updated_df = pd.concat([notif_df, new_notif], ignore_index=True)
    safe_update_worksheet(conn, "Notifications", updated_df)

def render_notification_inbox(user_id, conn):
    """
    Renders unread notifications specifically for user_id and updates Google Sheets directly.
    """
    try:
        # Read live data from Google Sheets without caching
        notif_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception:
        return

    if notif_df is None or notif_df.empty:
        return

    # 1. Normalize column headers
    notif_df.columns = [str(col).strip() for col in notif_df.columns]

    # 2. Ensure all required columns exist
    required_cols = ['notif_id', 'recipient_id', 'message', 'request_id', 'is_read']
    for col in required_cols:
        if col not in notif_df.columns:
            notif_df[col] = ""

    # Force columns to string object types to avoid float64 type mismatch errors
    for col in notif_df.columns:
        notif_df[col] = notif_df[col].astype("object")

    user_id_str = str(user_id).strip()

    # 3. Clean recipient IDs and Notification IDs as clean strings
    notif_df['recipient_id'] = notif_df['recipient_id'].fillna("").astype(str).str.strip()
    notif_df['notif_id'] = notif_df['notif_id'].fillna("").astype(str).str.strip()

    # 4. Robust Boolean Conversion for 'is_read'
    # Handles Python bool (True/False), Strings ("TRUE"/"FALSE"), and Ints (1/0)
    def parse_is_read(val):
        if pd.isna(val):
            return False
        if isinstance(val, bool):
            return val
        val_str = str(val).strip().upper()
        return val_str in ['TRUE', '1', 'YES', 'READ']

    notif_df['is_read_bool'] = notif_df['is_read'].apply(parse_is_read)

    # 5. Session state tracking for instant UI dismissal
    if "dismissed_notifs" not in st.session_state:
        st.session_state.dismissed_notifs = set()

    # 6. Filter ONLY true unread items for this user
    unread_mask = (
        (notif_df['recipient_id'] == user_id_str) & 
        (~notif_df['is_read_bool']) & 
        (~notif_df['notif_id'].isin(st.session_state.dismissed_notifs))
    )
    
    user_unread = notif_df[unread_mask]

    if user_unread.empty:
        return

    count = len(user_unread)
    with st.container(border=True, key="panel-notifications"):
        ui.html_block(
            '<p class="card-title" style="margin:0 0 0.25rem">Updates '
            f'{ui.tag(f"{count} new", "blue")}</p>'
        )
        for orig_idx, row in user_unread.iterrows():
            notif_id = row['notif_id'] if row['notif_id'] else f"row_{orig_idx}"
            is_message = str(row['message']).startswith("New message from")
            request_id = str(row.get('request_id', '')).strip()
            col_msg, col_btn = st.columns([3, 1], vertical_alignment="center")

            with col_msg:
                ui.html_block(f'<p style="margin:0">{ui.esc(row["message"])}</p>')

            with col_btn:
                with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
                    open_clicked = is_message and request_id and st.button(
                        "Open", type="tertiary", key=f"btn_open_{notif_id}_{orig_idx}"
                    )
                    read_clicked = st.button("Mark read", type="tertiary", key=f"btn_mark_read_{notif_id}_{orig_idx}")

            if open_clicked or read_clicked:
                try:
                    # Hide immediately on client side
                    st.session_state.dismissed_notifs.add(notif_id)

                    # Explicitly ensure column is string-compatible before assignment
                    notif_df['is_read'] = notif_df['is_read'].astype("object")
                    notif_df.loc[orig_idx, 'is_read'] = 'TRUE'

                    # Drop temporary helper column before saving
                    save_df = notif_df.drop(columns=['is_read_bool'])

                    # Convert to plain strings for Google Sheets (blank cells stay blank, not "nan")
                    for col in save_df.columns:
                        save_df[col] = save_df[col].fillna("").astype(str)

                    # Save back to Google Sheets & clear Streamlit cache
                    safe_update_worksheet(conn, "Notifications", save_df)
                except Exception as e:
                    handle_db_error(e, "Could not update notification status.")
                else:
                    if open_clicked:
                        ui.open_thread(request_id)
                    st.rerun()
    st.space("small")
