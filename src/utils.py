import streamlit as st
import pandas as pd
import uuid
from datetime import datetime

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
    Google Sheets 60 req/min API quota limits.
    """
    return conn.read(worksheet=worksheet_name, ttl=ttl)

def safe_update_worksheet(conn, worksheet_name, df):
    """
    Updates Google Sheets and clears Streamlit's cache so fresh data loads immediately.
    """
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

def handle_db_error(e, fallback_msg):
    st.error(f"{fallback_msg} Error: {e}")

def render_dob_selector(key_prefix="dob"):
    """
    Renders standard dropdowns for selecting Date of Birth (Month, Day, Year)
    and returns a formatted string 'YYYY-MM-DD'.
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
        "notif_id": str(uuid.uuid4())[:8],
        "recipient_id": str(recipient_id).strip(),
        "message": str(message),
        "request_id": str(request_id),
        "is_read": "FALSE"
    }])

    updated_df = pd.concat([notif_df, new_notif], ignore_index=True)
    safe_update_worksheet(conn, "Notifications", updated_df)

def render_notification_inbox(user_id, conn):
    """
    Renders unread notifications specifically for user_id and provides a button to mark as read.
    """
    st.write("### Notifications")

    try:
        notif_df = fetch_worksheet_cached(conn, "Notifications", ttl=5)
    except Exception as e:
        st.caption("No notifications system found or failed to load.")
        return

    if notif_df.empty:
        st.info("No new notifications.")
        return

    user_id_str = str(user_id).strip()

    # Ensure required columns exist in dataframe
    for col in ['recipient_id', 'is_read', 'message', 'notif_id']:
        if col not in notif_df.columns:
            notif_df[col] = ""

    # Filter for unread notifications belonging ONLY to current user
    unread_mask = (
        (notif_df['recipient_id'].astype(str).str.strip() == user_id_str) & 
        (~notif_df['is_read'].astype(str).str.upper().isin(['TRUE', '1', 'YES', 'READ']))
    )
    user_unread = notif_df[unread_mask].copy()

    if user_unread.empty:
        st.info("No unread notifications.")
    else:
        for idx, row in user_unread.iterrows():
            col_msg, col_btn = st.columns([3.5, 1.2])
            
            with col_msg:
                st.info(f"📩 {row.get('message', 'Notification')}")
                
            with col_btn:
                notif_id = row.get('notif_id', idx)
                if st.button("Mark as Read", key=f"read_notif_{notif_id}"):
                    try:
                        notif_df['is_read'] = notif_df['is_read'].astype("object")
                        
                        target_idx = notif_df[notif_df['notif_id'].astype(str) == str(notif_id)].index
                        if not target_idx.empty:
                            notif_df.loc[target_idx, 'is_read'] = 'TRUE'
                        else:
                            notif_df.loc[idx, 'is_read'] = 'TRUE'

                        safe_update_worksheet(conn, "Notifications", notif_df)
                        st.success("Marked as read!")
                        st.rerun()
                    except Exception as e:
                        handle_db_error(e, "Could not update notification status.")
