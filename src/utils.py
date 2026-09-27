import streamlit as st
import pandas as pd
import numpy as np
import uuid
from datetime import datetime

def generate_secure_id(prefix=""):
    """
    Generates a unique short ID string.
    """
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{unique_id}" if prefix else unique_id

def clean_zip_display(zip_val):
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

def safe_update_worksheet(conn, worksheet_name, df):
    """
    Cleans out any NaN/inf values before updating Google Sheets to avoid
    JSON compliance errors, then clears Streamlit's cache.
    """
    clean_df = df.copy()
    clean_df = clean_df.replace([np.inf, -np.inf], np.nan).fillna("")
    
    conn.update(worksheet=worksheet_name, data=clean_df)
    st.cache_data.clear()

def handle_db_error(e, fallback_msg):
    st.error(f"{fallback_msg} Error: {e}")

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
    st.write("### Notifications")

    try:
        # Fetch fresh data from Google Sheets
        notif_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception as e:
        st.caption("No notifications system found or failed to load.")
        return

    if notif_df is None or notif_df.empty:
        st.info("No new notifications.")
        return

    # Store exact original row index before any filtering
    notif_df['_row_idx'] = notif_df.index

    # Ensure all required columns exist and are clean strings
    required_cols = ['notif_id', 'recipient_id', 'message', 'request_id', 'is_read']
    for col in required_cols:
        if col not in notif_df.columns:
            notif_df[col] = ""
        notif_df[col] = notif_df[col].fillna("").astype(str).str.strip()

    user_id_str = str(user_id).strip()

    # Filter unread notifications for current user
    unread_mask = (
        (notif_df['recipient_id'] == user_id_str) & 
        (~notif_df['is_read'].str.upper().isin(['TRUE', '1', 'YES', 'READ']))
    )
    user_unread = notif_df[unread_mask].copy()

    if user_unread.empty:
        st.info("No unread notifications.")
    else:
        for _, row in user_unread.iterrows():
            col_msg, col_btn = st.columns([3.5, 1.2])
            target_row = row['_row_idx']
            notif_id = row['notif_id'] if row['notif_id'] else str(target_row)
            
            with col_msg:
                st.info(f"📩 {row['message']}")
                
            with col_btn:
                if st.button("Mark as Read", key=f"btn_read_{notif_id}_{target_row}"):
                    try:
                        # Update 'is_read' on main DataFrame using original row index
                        notif_df.loc[target_row, 'is_read'] = 'TRUE'

                        # Remove internal row tracker before saving
                        save_df = notif_df.drop(columns=['_row_idx'])

                        # Save back to Google Sheets & clear Streamlit cache
                        safe_update_worksheet(conn, "Notifications", save_df)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        handle_db_error(e, "Could not update notification status.")
