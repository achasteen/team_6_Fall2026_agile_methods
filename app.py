import datetime
import math
import uuid
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
from pypostalcode import PostalCodeDatabase

# Initialize US Zipcode Search Engine
search_engine = SearchEngine()

# ---------------------------------------------------------
# PAGE CONFIG & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="Samaritan Services", layout="centered")

page_bg = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee");
    background-size: cover;
    background-position: center;
}

[data-testid="stVerticalBlock"] {
    background-color: rgba(255, 255, 255, 0.85);
    padding: 30px;
    border-radius: 12px;
    box-shadow: 0 0 10px rgba(0,0,0,0.2);
}

h1 {
    text-align: center;
    color: black;
    background-color: rgba(255, 255, 255, 0.9);
    padding: 10px 20px;
    border-radius: 8px;
    box-shadow: 0 0 8px rgba(0,0,0,0.3);
    font-family: 'Arial Black', sans-serif;
}

label {
    color: black !important;
    font-weight: bold;
}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)
st.title("Samaritan Services")

# Initialize Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "dashboard_view" not in st.session_state:
    st.session_state.dashboard_view = "menu"

# Date of Birth dropdown values
CURRENT_YEAR = datetime.date.today().year
YEARS = list(range(CURRENT_YEAR, 1899, -1))
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
DAYS = list(range(1, 32))

def render_dob_selector(key_prefix):
    st.write("**Date of Birth**")
    col_y, col_m, col_d = st.columns(3)
    with col_y:
        year = st.selectbox("Year", options=YEARS, index=26, key=f"{key_prefix}_year")
    with col_m:
        month = st.selectbox("Month", options=MONTHS, key=f"{key_prefix}_month")
    with col_d:
        day = st.selectbox("Day", options=DAYS, key=f"{key_prefix}_day")
    return f"{year}-{month}-{day}"

# ---------------------------------------------------------
# GEOGRAPHIC RADIUS HELPER
# ---------------------------------------------------------
def get_zip_distance(zip1, zip2):
    """Calculates straight-line distance in miles between two US zip codes."""
    z1 = search_engine.by_zipcode(str(zip1).strip())
    z2 = search_engine.by_zipcode(str(zip2).strip())

    if not z1 or not z2 or not z1.lat or not z2.lat:
        return None

    lat1, lon1 = math.radians(z1.lat), math.radians(z1.lng)
    lat2, lon2 = math.radians(z2.lat), math.radians(z2.lng)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return round(3958.8 * c, 1)

# ---------------------------------------------------------
# NOTIFICATION HELPERS
# ---------------------------------------------------------
def send_browser_push(title, body):
    """Triggers a native browser push notification via JavaScript."""
    js_code = f"""
    <script>
    if ("Notification" in window) {{
        if (Notification.permission === "granted") {{
            new Notification("{title}", {{ body: "{body}" }});
        }} else if (Notification.permission !== "denied") {{
            Notification.requestPermission().then(p => {{
                if (p === "granted") new Notification("{title}", {{ body: "{body}" }});
            }});
        }}
    }}
    </script>
    """
    components.html(js_code, height=0)

def create_notification(recipient_id, message, notif_type):
    """Appends a new notification row to the Google Sheets Notifications tab."""
    try:
        notif_existing_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception:
        notif_existing_df = pd.DataFrame(columns=[
            "notification_id", "recipient_user_id", "message", "type", "created_at", "is_read"
        ])
    
    new_notif = pd.DataFrame([{
        "notification_id": str(uuid.uuid4())[:8],
        "recipient_user_id": str(recipient_id),
        "message": message,
        "type": notif_type,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_read": False
    }])
    
    updated_notifs_df = pd.concat([notif_existing_df, new_notif], ignore_index=True)
    conn.update(worksheet="Notifications", data=updated_notifs_df)

def render_notification_inbox(user_id):
    """Renders the Notification Inbox panel inside the user profile."""
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
        st.info("You have no notifications.")
        return

    user_notifs = user_notifs.sort_values(by="created_at", ascending=False)
    unread_count = len(user_notifs[user_notifs["is_read"] == False])

    if unread_count > 0:
        st.caption(f"You have **{unread_count} unread** notification(s).")

    for idx, row in user_notifs.iterrows():
        is_unread = not row["is_read"]
        badge = "🔴 " if is_unread else "⚪ "

        with st.container():
            col_content, col_action = st.columns([4, 1])

            with col_content:
                st.markdown(f"{badge}**{row['message']}**")
                st.caption(f"Received: {row['created_at']}")

            with col_action:
                if is_unread:
                    if st.button("Mark Read", key=f"read_{row['notification_id']}"):
                        notifs_df.loc[notifs_df["notification_id"] == row["notification_id"], "is_read"] = True
                        conn.update(worksheet="Notifications", data=notifs_df)
                        st.rerun()

        st.divider()

# ---------------------------------------------------------
# LOGGED-IN DASHBOARD VIEW
# ---------------------------------------------------------
if st.session_state.logged_in:
    user_info = st.session_state.current_user
    
    st.subheader(f"Welcome, {user_info['first_name']} {user_info['last_name']}")
    st.caption(f"Role: {user_info['role']} | User ID: {user_info['user_id']} | Zip: {user_info.get('zip', 'N/A')}")

    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.dashboard_view = "menu"
        st.rerun()

    st.divider()

    # NOTIFICATION INBOX PANEL
    with st.expander("🔔 My Notifications", expanded=True):
        render_notification_inbox(user_info["user_id"])

    st.divider()

    # DASHBOARD NAVIGATION MENU
    if st.session_state.dashboard_view == "menu":
        st.write("### Choose an Action")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Start New Request", use_container_width=True):
                st.session_state.dashboard_view = "new_request"
                st.rerun()
                
        with col2:
            if st.button("All Open Requests", use_container_width=True):
                st.session_state.dashboard_view = "accept_request"
                st.rerun()

        with col3:
            if st.button("50-Mile Radius Search", use_container_width=True):
                st.session_state.dashboard_view = "matched_requests"
                st.rerun()

    # VIEW: CREATE NEW REQUEST
    elif st.session_state.dashboard_view == "new_request":
        st.write("### Start a New Request")
        req_name = st.text_input("Request Name/Title", key="nr_name")
        req_zip = st.text_input("Zip Code", value=str(user_info.get("zip", "")), key="nr_zip")
        req_description = st.text_area("Description", key="nr_description")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Back"):
                st.session_state.dashboard_view = "menu"
                st.rerun()
        with col_b:
            if st.button("Submit Request"):
                if req_name and req_zip and req_description:
                    try:
                        req_existing_df = conn.read(worksheet="Requests", ttl=0)
                    except Exception:
                        req_existing_df = pd.DataFrame()

                    request_id = str(uuid.uuid4())[:8]

                    req_new_row = pd.DataFrame([{
                        "request_id": request_id,
                        "request_name": req_name,
                        "zip": req_zip,
                        "description": req_description,
                        "requested_by": f"{user_info['first_name']} {user_info['last_name']}",
                        "requested_by_name": f"{user_info['first_name']} {user_info['last_name']}",
                        "requested_by_id": user_info["user_id"],
                        "status": "pending",
                        "accepted_by": None,
                        "accepted_by_name": None,
                        "accepted_by_id": None
                    }])

                    req_updated_df = pd.concat([req_existing_df, req_new_row], ignore_index=True)
                    conn.update(worksheet="Requests", data=req_updated_df)

                    st.session_state.dashboard_view = "menu"
                    st.success("Request submitted successfully!")
                    st.rerun()
                else:
                    st.error("Please fill out all fields.")

    # VIEW: ACCEPT ALL OPEN REQUESTS
    elif st.session_state.dashboard_view == "accept_request":
        st.write("### All Pending Requests")

        try:
            all_requests_df = conn.read(worksheet="Requests", ttl=0)
            pending_requests = all_requests_df[
                (all_requests_df['status'] == "pending") & 
                (all_requests_df['requested_by_id'].astype(str) != str(user_info["user_id"]))
            ].copy()
        except Exception:
            pending_requests = pd.DataFrame()

        if pending_requests.empty:
            st.write("No pending requests right now.")
        else:
            for idx, row in pending_requests.iterrows():
                with st.container():
                    st.write(f"**Request:** {row['request_name']}")
                    st.write(f"**Requested By:** {row['requested_by_name']}")
                    st.write(f"**Zip:** {row['zip']}")
                    st.write(f"**Description:** {row['description']}")

                    if st.button("Accept", key=f"accept_all_{row['request_id']}"):
                        samaritan_name = f"{user_info['first_name']} {user_info['last_name']}"
                        req_title = row['request_name']

                        # 1. Update Request status in Google Sheets
                        all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'status'] = 'accepted'
                        all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'accepted_by_name'] = samaritan_name
                        all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'accepted_by_id'] = user_info['user_id']
                        conn.update(worksheet="Requests", data=all_requests_df)

                        # 2. Add notification for Requester
                        create_notification(
                            recipient_id=row['requested_by_id'],
                            message=f"Your request '{req_title}' was accepted by Samaritan {samaritan_name}!",
                            notif_type="request_accepted"
                        )

                        # 3. Add notification for Samaritan
                        create_notification(
                            recipient_id=user_info['user_id'],
                            message=f"You accepted '{req_title}' posted by {row['requested_by_name']}.",
                            notif_type="accepted_confirmation"
                        )

                        # 4. Trigger browser push
                        send_browser_push("Request Accepted!", f"You accepted '{req_title}'")

                        st.success("Request accepted and notification logged!")
                        st.rerun()

                st.divider()

        if st.button("Back to Menu"):
            st.session_state.dashboard_view = "menu"
            st.rerun()

    # VIEW: 50-MILE RADIUS MATCHED REQUESTS
    elif st.session_state.dashboard_view == "matched_requests":
        st.write("### 📍 Requests Within 50 Miles")

        user_zip = str(user_info.get("zip", "")).strip()

        col_zip, col_rad = st.columns([2, 1])
        with col_zip:
            search_zip = st.text_input("Center Zip Code", value=user_zip, key="radius_zip_input")
        with col_rad:
            max_distance = st.slider("Max Miles", min_value=1, max_value=50, value=50, step=1)

        try:
            all_requests_df = conn.read(worksheet="Requests", ttl=0)
            pending_df = all_requests_df[
                (all_requests_df['status'] == "pending") & 
                (all_requests_df['requested_by_id'].astype(str) != str(user_info["user_id"]))
            ].copy()
        except Exception:
            pending_df = pd.DataFrame()

        if pending_df.empty or not search_zip:
            st.info("No pending requests available to search.")
        else:
            nearby_requests = []
            for idx, row in pending_df.iterrows():
                dist = get_zip_distance(search_zip, row['zip'])
                if dist is not None and dist <= max_distance:
                    row_dict = row.to_dict()
                    row_dict['distance_miles'] = dist
                    nearby_requests.append(row_dict)

            if not nearby_requests:
                st.warning(f"No pending requests found within **{max_distance} miles** of zip **{search_zip}**.")
            else:
                st.success(f"Found **{len(nearby_requests)}** request(s) within **{max_distance} miles**:")
                
                # Sort by closest distance first
                nearby_requests.sort(key=lambda x: x['distance_miles'])

                for req in nearby_requests:
                    with st.container():
                        st.write(f"**Request:** {req['request_name']}")
                        st.write(f"**Requested By:** {req['requested_by_name']}")
                        st.write(f"**Location:** Zip {req['zip']} (**{req['distance_miles']} miles away**)")
                        st.write(f"**Description:** {req['description']}")

                        if st.button("Accept Request", key=f"accept_rad_{req['request_id']}"):
                            samaritan_name = f"{user_info['first_name']} {user_info['last_name']}"
                            req_title = req['request_name']

                            all_requests_df.loc[all_requests_df['request_id'] == req['request_id'], 'status'] = 'accepted'
                            all_requests_df.loc[all_requests_df['request_id'] == req['request_id'], 'accepted_by_name'] = samaritan_name
                            all_requests_df.loc[all_requests_df['request_id'] == req['request_id'], 'accepted_by_id'] = user_info['user_id']
                            conn.update(worksheet="Requests", data=all_requests_df)

                            create_notification(
                                recipient_id=req['requested_by_id'],
                                message=f"Your request '{req_title}' was accepted by Samaritan {samaritan_name}!",
                                notif_type="request_accepted"
                            )
                            create_notification(
                                recipient_id=user_info['user_id'],
                                message=f"You accepted '{req_title}' posted by {req['requested_by_name']}.",
                                notif_type="accepted_confirmation"
                            )

                            send_browser_push("Request Accepted!", f"You accepted '{req_title}'")
                            st.success("Request accepted!")
                            st.rerun()

                    st.divider()

        if st.button("Back to Menu"):
            st.session_state.dashboard_view = "menu"
            st.rerun()

# ---------------------------------------------------------
# LOGGED-OUT VIEW (LOGIN OR REGISTER)
# ---------------------------------------------------------
else:
    page_action = st.radio(
        "Welcome! Please select an option:",
        options=["Login", "Register"],
        horizontal=True,
    )

    st.divider()

    # LOGIN VIEW
    if page_action == "Login":
        st.subheader("Login to Your Account")

        login_id = st.text_input("User ID", key="login_user_id")
        login_pass = st.text_input("Password", type="password", key="login_password")

        if st.button("Log In"):
            try:
                user_existing_df = conn.read(worksheet="Users", ttl=0)
                user_match = user_existing_df[user_existing_df['user_id'].astype(str) == str(login_id)]

                if not user_match.empty:
                    stored_pass = str(user_match['password'].values[0])
                    if str(login_pass) == stored_pass:
                        st.session_state.logged_in = True
                        st.session_state.current_user = {
                            "user_id": login_id,
                            "first_name": user_match['first_name'].values[0],
                            "last_name": user_match['last_name'].values[0],
                            "role": user_match['role'].values[0],
                            "zip": user_match['zip'].values[0] if 'zip' in user_match.columns else "",
                        }
                        st.rerun()
                    else:
                        st.error("Incorrect Password.")
                else:
                    st.error("Invalid User ID.")
            except Exception as e:
                st.error("Could not reach Users database. Please check Google Sheets setup.")

    # REGISTER VIEW
    elif page_action == "Register":
        st.subheader("Account Registration")
        st.caption("Please fill out the information below to create your profile.")
        st.caption("This is for educational purposes only, please don't use real information.")

        role = st.selectbox("I am registering as a:", options=["User", "Samaritan"], key="account_role")

        reg_user_id = st.text_input("User ID", key="reg_user_id")
        reg_password = st.text_input("Password", type="password", key="reg_password")

        first_name = st.text_input("First Name", key="reg_first")
        middle_name = st.text_input("Middle Name or Initial", key="reg_middle")
        last_name = st.text_input("Last Name", key="reg_last")
        
        dob_str = render_dob_selector("reg_dob")
        
        city = st.text_input("City", key="reg_city")
        state = st.text_input("State", key="reg_state")
        zip_code = st.text_input("Zip Code", key="reg_zip")
        age = st.number_input("Age", min_value=18, max_value=120, key="reg_age")

        if role == "Samaritan":
            services = st.text_area("Services you would like to offer", key="reg_services")
            uploaded_file = st.file_uploader("Upload a picture of driver's license", type=["jpeg", "jpg", "png"], key="reg_dl_pic")
        else:
            services = ""
            uploaded_file = st.file_uploader("Upload any form of ID to verify information", type=["jpeg", "jpg", "png", "pdf"], key="reg_user_id_doc")

        if st.button("Submit Registration"):
            if not reg_user_id or not reg_password:
                st.error("Please fill in both User ID and Password.")
            else:
                try:
                    user_existing_df = conn.read(worksheet="Users", ttl=0)
                except Exception:
                    user_existing_df = pd.DataFrame(columns=[
                        "user_id", "password", "role", "first_name", "last_name", "city", "state", "zip", "services"
                    ])

                if reg_user_id in user_existing_df["user_id"].astype(str).values:
                    st.error(f"User ID '{reg_user_id}' is already taken. Please choose another one.")
                else:
                    user_new_row = pd.DataFrame([{
                        "user_id": reg_user_id,
                        "password": reg_password,
                        "role": role,
                        "first_name": first_name or role,
                        "last_name": last_name or "User",
                        "city": city,
                        "state": state,
                        "zip": zip_code,
                        "services": services
                    }])

                    user_updated_df = pd.concat([user_existing_df, user_new_row], ignore_index=True)
                    conn.update(worksheet="Users", data=user_updated_df)
                    st.success(f"Registered successfully as {role}! You can now log in.")
