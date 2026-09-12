import datetime
import streamlit as st

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

label {
    color: black !important;
    font-weight: bold;
}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)

st.title("Samaritan Services")

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
        st.rerun()

    st.divider()

    st.write("### Choose an Action")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Start New Request", use_container_width=True):
            st.info("Start New Request workflow selected.")

    with col2:
        if st.button("Accept Existing Request", use_container_width=True):
            st.info("Accept Existing Request workflow selected.")

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
            users = st.session_state.users_db
            if login_id in users and users[login_id]["password"] == login_pass:
                st.session_state.logged_in = True
                st.session_state.current_user = users[login_id]
                st.rerun()
            else:
                st.error("Invalid User ID or Password.")

    # SINGLE UNIFIED REGISTER PAGE
    elif page_action == "Register":
        st.subheader("Account Registration")
        st.caption("Please fill out the information below to create your profile.")

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
            uploaded_file = st.file_uploader(
                "Upload a picture of driver's license",
                type=["jpeg", "jpg", "png"],
                key="reg_dl_pic"
            )
        else:
            uploaded_file = st.file_uploader(
                "Upload any form of ID to verify information",
                type=["jpeg", "jpg", "png", "pdf"],
                key="reg_user_id_doc"
            )

        if st.button("Submit Registration"):
            if reg_user_id and reg_password:
                st.session_state.users_db[reg_user_id] = {
                    "password": reg_password,
                    "role": role,
                    "first_name": first_name or role,
                    "last_name": last_name or "User",
                    "city": city,
                    "state": state,
                }
                st.success(f"Registered successfully as {role}! You can now log in.")
            else:
                st.error("Please fill in both User ID and Password.")
