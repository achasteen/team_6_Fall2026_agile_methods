import streamlit as st
import datetime
import pandas as pd
import math
import streamlit.components.v1 as components
import uuid
import json
from pyzipcode import ZipCodeDatabase

# Initialize PyZipCode Database
pcdb = ZipCodeDatabase()

def generate_secure_id():
    """Returns a full, unguessable UUIDv4 string for use as a record ID.

    IDs must never be truncated: short IDs are guessable and open the app
    to enumeration / Insecure Direct Object Reference (IDOR) attacks.
    """
    return str(uuid.uuid4())


def clean_zip_display(zip_val):
    """Formats zip values to remove decimal points from pandas parsing."""
    if pd.isna(zip_val) or not zip_val:
        return ""
    return str(zip_val).split('.')[0].strip().zfill(5)


def render_dob_selector(key_prefix):
    """Renders year, month, day selectors for Date of Birth."""
    CURRENT_YEAR = datetime.date.today().year
    YEARS = list(range(CURRENT_YEAR, 1899, -1))
    MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    DAYS = list(range(1, 32))
    st.write("**Date of Birth**")
    col_y, col_m, col_d = st.columns(3)
    with col_y:
        year = st.selectbox("Year", options=YEARS, index=26, key=f"{key_prefix}_year")
    with col_m:
        month = st.selectbox("Month", options=MONTHS, key=f"{key_prefix}_month")
    with col_d:
        day = st.selectbox("Day", options=DAYS, key=f"{key_prefix}_day")
    return f"{year}-{month}-{day}"


def get_zip_distance(zip1, zip2):
    """Calculates straight-line distance in miles between two US zip codes."""
    try:
        z1_str = clean_zip_display(zip1)
        z2_str = clean_zip_display(zip2)

        if z1_str == z2_str and len(z1_str) == 5:
            return 0.0

        z1 = pcdb[z1_str]
        z2 = pcdb[z2_str]

        if not z1 or not z2:
            return None

        lat1, lon1 = math.radians(z1.latitude), math.radians(z1.longitude)
        lat2, lon2 = math.radians(z2.latitude), math.radians(z2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return round(3958.8 * c, 1)
    except Exception:
        return None


def send_browser_push(title, body):
    """Triggers a native browser push notification via JavaScript safely."""
    safe_title = json.dumps(str(title))
    safe_body = json.dumps(str(body))
    js_code = f"""
    <script>
    if ("Notification" in window) {{
        if (Notification.permission === "granted") {{
            new Notification({safe_title}, {{ body: {safe_body} }});
        }} else if (Notification.permission !== "denied") {{
            Notification.requestPermission().then(p => {{
                if (p === "granted") new Notification({safe_title}, {{ body: {safe_body} }});
            }});
        }}
    }}
    </script>
    """
    components.html(js_code, height=0)


def create_notification(recipient_id, message, notif_type, conn):
    """Appends a new notification row to the Google Sheets Notifications tab."""
    try:
        notif_existing_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception:
        notif_existing_df = pd.DataFrame(columns=[
            "notification_id", "recipient_user_id", "message", "type", "created_at", "is_read"
        ])

    new_notif = pd.DataFrame([{
        "notification_id": generate_secure_id(),
        "recipient_user_id": str(recipient_id),
        "message": message,
        "type": notif_type,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_read": "FALSE"
    }])

    updated_notifs_df = pd.concat([notif_existing_df, new_notif], ignore_index=True)
    conn.update(worksheet="Notifications", data=updated_notifs_df)


def render_notification_inbox(user_id, conn):
    """Renders the Notification Inbox panel inside the dashboard."""
    st.write("### 🔔 Notification Inbox")

    try:
        notifs_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception:
        st.warning("Could not load Notifications worksheet.")
        return

    if notifs_df.empty or "recipient_user_id" not in notifs_df.columns:
        st.info("No notifications yet.")
        return

    user_notifs = notifs_df[notifs_df["recipient_user_id"].astype(str) == str(user_id)].copy()

    if user_notifs.empty:
        st.info("You have no notifications right now.")
        return

    user_notifs = user_notifs.sort_values(by="created_at", ascending=False)
    
    unread_count = len(user_notifs[~user_notifs["is_read"].astype(str).str.upper().isin(["TRUE", "1", "1.0"])])

    if unread_count > 0:
        st.caption(f"You have **{unread_count} unread** notification(s).")

    for idx, row in user_notifs.iterrows():
        is_read_val = str(row["is_read"]).upper() in ["TRUE", "1", "1.0"]
        badge = "⚪ " if is_read_val else "🔴 "

        with st.container():
            col_content, col_action = st.columns([4, 1])

            with col_content:
                st.markdown(f"{badge}**{row['message']}**")
                st.caption(f"Received: {row['created_at']}")

            with col_action:
                if not is_read_val:
                    if st.button("Mark Read", key=f"read_{row['notification_id']}"):
                        notifs_df["is_read"] = notifs_df["is_read"].astype(str)
                        notifs_df.loc[notifs_df["notification_id"].astype(str) == str(row["notification_id"]), "is_read"] = "TRUE"
                        conn.update(worksheet="Notifications", data=notifs_df)
                        st.rerun()

        st.divider()
