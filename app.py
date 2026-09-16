import datetime
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Page config
st.set_page_config(page_title="Samaritan Services", layout="centered")

# Custom CSS for background and styling
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

[data-testid="stVerticalBlock"] p,
[data-testid="stVerticalBlock"] span,
[data-testid="stVerticalBlock"] label,
[data-testid="stVerticalBlock"] li,
[data-testid="stVerticalBlock"] h1,
[data-testid="stVerticalBlock"] h2,
[data-testid="stVerticalBlock"] h3,
[data-testid="stVerticalBlock"] h4 {
    color: black !important;
    font-weight: bold;
}

[data-testid="stVerticalBlock"] button {
    color: black !important;
    background-color: white !important;
    border: 1px solid #999 !important;
}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)

st.title("Samaritan Services")
conn = st.connection("gsheets", type=GSheetsConnection)
# conn = st.connection("gsheets", type=GSheetsConnection)

# example usage
# if st.button("Test write to sheet"):
#     # Read existing data (if the sheet has headers already)
#     existing_df = conn.read(worksheet="Sheet1")
#
#     # Create a new row
#     new_row = pd.DataFrame([{"message": "hello world"}])
#
#     # Append it
#     updated_df = pd.concat([existing_df, new_row], ignore_index=True)
#     conn.update(worksheet="Sheet1", data=updated_df)
#
#     st.success("Wrote 'hello world' to the sheet!")
#     st.dataframe(updated_df)


# Initialize Demo Accounts Database in Session State
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "test_samaritan": {
            "password": "test_samaritan",
            "role": "Samaritan",
            "first_name": "Sam",
            "last_name": "Goodman",
            "city": "Seattle",
            "state": "WA",
        },
        "test_user": {
            "password": "test_user",
            "role": "User",
            "first_name": "Jane",
            "last_name": "Doe",
            "city": "Seattle",
            "state": "WA",
        },
    }

# Track authentication state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# In-memory store for submitted requests
if "requests_db" not in st.session_state:
    st.session_state.requests_db = []

# Which sub-view of the logged-in dashboard is showing
if "dashboard_view" not in st.session_state:
    st.session_state.dashboard_view = "menu"

# Date ranges for DOB dropdowns (1900 to 2026)
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
        year = st.selectbox("Year", options=YEARS, index=26, key=f"{key_prefix}_year")  # Default ~2000
    with col_m:
        month = st.selectbox("Month", options=MONTHS, key=f"{key_prefix}_month")
    with col_d:
        day = st.selectbox("Day", options=DAYS, key=f"{key_prefix}_day")
    return f"{year}-{month}-{day}"


# ---------------------------------------------------------
# LOGGED-IN DASHBOARD VIEW
# ---------------------------------------------------------
if st.session_state.logged_in:
    user_info = st.session_state.current_user

    st.subheader(f"Logged in as: {user_info['first_name']} {user_info['last_name']}")
    st.caption(f"Role: {user_info['role']}")

    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.dashboard_view = "menu"
        st.rerun()

    st.divider()

    if st.session_state.dashboard_view == "menu":
        st.write("### Choose an Action")

        if user_info["role"] == "User":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Start New Request", use_container_width=True):
                    st.session_state.dashboard_view = "new_request_form"
                    st.rerun()
            with col2:
                if st.button("My Requests", use_container_width=True):
                    st.session_state.dashboard_view = "my_requests"
                    st.rerun()
        else:  # Samaritan
            if st.button("Accept Existing Request", use_container_width=True):
                st.session_state.dashboard_view = "accept_request_list"
                st.rerun()

    elif st.session_state.dashboard_view == "new_request_form":
        if user_info["role"] != "User":
            st.session_state.dashboard_view = "menu"
            st.rerun()
        else:
            st.write("### Start New Request")
            st.text_input("Name", key="nr_name")
            st.text_input("Zip", key="nr_zip")
            st.text_area("Description", key="nr_description")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Cancel"):
                    st.session_state.dashboard_view = "menu"
                    st.rerun()
            with col_b:
                if st.button("Submit Request"):
                    if st.session_state.nr_name and st.session_state.nr_zip and st.session_state.nr_description:
                        req_existing_df = conn.read(worksheet="Requests", ttl=0)
                        request_id = 0
                        if request_id in req_existing_df['request_id'].values:
                            while request_id in req_existing_df['request_id'].values:
                                request_id += 1
                        req_new_row = pd.DataFrame([{
                            "request_id": request_id,
                            "request_name": st.session_state.nr_name,
                            "zip": st.session_state.nr_zip,
                            "description": st.session_state.nr_description,
                            "requested_by_name": f"{user_info['first_name']} {user_info['last_name']}",
                            "requested_by_id": user_info["user_id"],
                            "status": "pending"
                        }])
                        req_updated_df = pd.concat([req_existing_df, req_new_row], ignore_index=True)
                        conn.update(worksheet="Requests", data=req_updated_df)
                        # st.session_state.requests_db.append({
                        #     "name": st.session_state.nr_name,
                        #     "zip": st.session_state.nr_zip,
                        #     "description": st.session_state.nr_description,
                        #     "requested_by": f"{user_info['first_name']} {user_info['last_name']}",
                        #     "requested_by_id": user_info["user_id"],
                        #     "status": "pending",
                        #     "accepted_by": None,
                        # })
                        st.session_state.dashboard_view = "menu"
                        st.success("Request submitted!")
                        st.rerun()
                    else:
                        st.error("Please fill in all fields.")

    elif st.session_state.dashboard_view == "my_requests":
        if user_info["role"] != "User":
            st.session_state.dashboard_view = "menu"
            st.rerun()
        else:
            st.write("### My Requests")
            all_requests_df = conn.read(worksheet="Requests", ttl=0)
            my_requests = all_requests_df[all_requests_df['requested_by_id'] == user_info["user_id"]].copy()
            # my_requests = [
            #     r for r in st.session_state.requests_db
            #     if r["requested_by_id"] == user_info["user_id"]
            # ]

            if len(my_requests) < 1:
                st.write("You haven't submitted any requests yet.")
            else:
                for idx, row in my_requests.iterrows():
                    with st.container():
                        st.write(f"**Name:** {row['request_name']}")
                        st.write(f"**Zip:** {row['zip']}")
                        st.write(f"**Description:** {row['description']}")
                        st.write(f"**Status:** {row['status'].capitalize()}")
                        if row["status"] == "accepted":
                            st.write(f"**Accepted by:** {row['accepted_by_name']}")
                        st.divider()

            if st.button("Back"):
                st.session_state.dashboard_view = "menu"
                st.rerun()

    elif st.session_state.dashboard_view == "accept_request_list":
        if user_info["role"] != "Samaritan":
            st.session_state.dashboard_view = "menu"
            st.rerun()
        else:
            st.write("### Pending Requests")
            all_requests_df = conn.read(worksheet="Requests", ttl=0)
            all_requests_df['accepted_by_name'] = all_requests_df['accepted_by_name'].astype(str)
            all_requests_df['accepted_by_id'] = all_requests_df['accepted_by_id'].astype(str)
            pending_requests = all_requests_df[(all_requests_df['status'] == "pending") & (all_requests_df['requested_by_id'] != user_info["user_id"])].copy()
            # pending_requests = [
            #     (idx, r) for idx, r in enumerate(st.session_state.requests_db)
            #     if r["status"] == "pending" and r["requested_by_id"] != user_info["user_id"]
            # ]

            if len(pending_requests) < 1:
                st.write("No pending requests right now.")
            else:
                for idx, row in pending_requests.iterrows():
                    with st.container():
                        st.write(f"**Name:** {row['request_name']}")
                        st.write(f"**Zip:** {row['zip']}")
                        st.write(f"**Description:** {row['description']}")
                        if st.button("Accept", key=f"accept_{idx}"):
                            all_requests_df.at[idx,'status'] = 'accepted'
                            all_requests_df.at[idx, 'accepted_by_name'] = f"{user_info['first_name']} {user_info['last_name']}"
                            all_requests_df.at[idx, 'accepted_by_id'] = user_info['user_id']
                            conn.update(worksheet="Requests", data=all_requests_df)
                            st.success("Request accepted!")
                            st.rerun()
                        st.divider()

                # for idx, req in pending_requests:
                #     with st.container():
                #         st.write(f"**Name:** {req['name']}")
                #         st.write(f"**Zip:** {req['zip']}")
                #         st.write(f"**Description:** {req['description']}")
                #         if st.button("Accept", key=f"accept_{idx}"):
                #             req["status"] = "accepted"
                #             req["accepted_by"] = f"{user_info['first_name']} {user_info['last_name']}"
                #             st.success("Request accepted!")
                #             st.rerun()
                #         st.divider()

            if st.button("Back"):
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

    # LOGIN PAGE
    if page_action == "Login":
        st.subheader("Login to Your Account")

        login_id = st.text_input("User ID", key="login_user_id")
        login_pass = st.text_input("Password", type="password", key="login_password")

        if st.button("Log In"):
            # users = st.session_state.users_db
            user_existing_df = conn.read(worksheet="Users", ttl=0)
            if login_id in user_existing_df['user_id'].values:
                stored_pass = user_existing_df.loc[user_existing_df['user_id'] == login_id,'password'].values[0]
                if login_pass == stored_pass:
                    st.session_state.logged_in = True
                    st.session_state.current_user = {
                    "first_name":user_existing_df.loc[user_existing_df['user_id'] == login_id,'first_name'].values[0],
                    "last_name":user_existing_df.loc[user_existing_df['user_id'] == login_id,'last_name'].values[0],
                    "role":user_existing_df.loc[user_existing_df['user_id'] == login_id,'role'].values[0],
                    "user_id": login_id}
                    st.rerun()
                else:
                    st.error("Incorrect Password.")
            else:
                st.error("Invalid User ID.")

    # SINGLE UNIFIED REGISTER PAGE
    elif page_action == "Register":
        st.subheader("Account Registration")
        st.caption("Please fill out the information below to create your profile.")
        st.caption("This is for educational purposes only, please don't use real information.")

        # Single Role Selector Field
        role = st.selectbox(
            "I am registering as a:",
            options=["User", "Samaritan"],
            key="account_role"
        )

        # Credentials
        reg_user_id = st.text_input("User ID", key="reg_user_id")
        reg_password = st.text_input("Password", type="password", key="reg_password")

        # Personal Details
        first_name = st.text_input("First Name", key="reg_first")
        middle_name = st.text_input("Middle Name or Initial", key="reg_middle")
        last_name = st.text_input("Last Name", key="reg_last")

        dob_str = render_dob_selector("reg_dob")

        city = st.text_input("City", key="reg_city")
        state = st.text_input("State", key="reg_state")
        zip_code = st.text_input("Zip", key="reg_zip")
        age = st.number_input("Age", min_value=18, max_value=120, key="reg_age")

        # Dynamic Fields based on Selected Role
        if role == "Samaritan":
            services = st.text_area("Services you would like to offer", key="reg_services")
            # uploaded_file = st.file_uploader(
            #     "Upload a picture of driver's license",
            #     type=["jpeg", "jpg", "png"],
            #     key="reg_dl_pic"
            # )
        else:
            services = ""
            # uploaded_file = st.file_uploader(
            #     "Upload any form of ID to verify information",
            #     type=["jpeg", "jpg", "png", "pdf"],
            #     key="reg_user_id_doc"
            # )

        if st.button("Submit Registration"):
            # Read existing data (if the sheet has headers already)
            user_existing_df = conn.read(worksheet="Users", ttl=0)
            if reg_user_id not in user_existing_df["user_id"].values:
                if reg_user_id and reg_password:
                    # Create a new row
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

                    # Append it
                    user_updated_df = pd.concat([user_existing_df, user_new_row], ignore_index=True)
                    conn.update(worksheet="Users", data=user_updated_df)
                    # st.session_state.users_db[reg_user_id] = {
                    #     "password": reg_password,
                    #     "role": role,
                    #     "first_name": first_name or role,
                    #     "last_name": last_name or "User",
                    #     "city": city,
                    #     "state": state,
                    # }
                    st.success(f"Registered successfully as {role}! You can now log in.")
                else:
                    st.error("Please fill in both User ID and Password.")
            else:
                st.error(f"User ID: {reg_user_id} is already taken. Please choose another one.")
