import streamlit as st
from streamlit_gsheets import GSheetsConnection
import src.views.logged_out_login as logged_out_login
import src.views.logged_out_register as logged_out_register
import src.views.logged_in_user as logged_in_user
import src.views.logged_in_samaritan as logged_in_samaritan
import src.utils as utils

# Initialize Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------------------------------------------------
# PAGE CONFIG & STYLING
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "dashboard_view" not in st.session_state:
    st.session_state.dashboard_view = "menu"


if st.session_state.logged_in:
# ---------------------------------------------------------
# LOGGED-IN DASHBOARD VIEW
# ---------------------------------------------------------
    user_info = st.session_state.current_user
    user_role = str(user_info.get("role", "User"))
    st.subheader(f"Welcome, {user_info['first_name']} {user_info['last_name']} ({user_role})")
    st.caption(f"User ID: {user_info['user_id']} | Zip Code: {utils.clean_zip_display(user_info.get('zip', 'N/A'))}")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.dashboard_view = "menu"
        st.rerun()
    st.divider()

    # NOTIFICATION INBOX PANEL
    with st.expander("🔔 Notification Inbox", expanded=True):
        utils.render_notification_inbox(user_info["user_id"], conn)

    st.divider()

    if st.session_state.dashboard_view == "menu":
        st.write("### Choose an Action")

        # USER DASHBOARD OPTIONS
        if user_role.lower() == "user":
            logged_in_user.render_menu()
        elif user_role.lower() == "samaritan":
            logged_in_samaritan.render_menu()

    # ---------------------------------------------------------
    # USER VIEW 1: START NEW REQUEST
    # ---------------------------------------------------------
    elif st.session_state.dashboard_view == "new_request":
        logged_in_user.render_new_request(user_info, conn)

    # ---------------------------------------------------------
    # USER VIEW 2: SEE STATUS OF MY REQUESTS
    # ---------------------------------------------------------
    elif st.session_state.dashboard_view == "user_request_status":
        logged_in_user.render_user_status(user_info, conn)

    # ---------------------------------------------------------
    # SAMARITAN VIEW 1: ACCEPT NEW REQUEST
    # ---------------------------------------------------------
    elif st.session_state.dashboard_view == "accept_request":
        logged_in_samaritan.render_accept_request(user_info, conn)

    # ---------------------------------------------------------
    # SAMARITAN VIEW 2: SEE ACCEPTED REQUESTS
    # ---------------------------------------------------------
    elif st.session_state.dashboard_view == "my_accepted_requests":
        logged_in_samaritan.render_accepted_requests(user_info, conn)

    # ---------------------------------------------------------
    # SAMARITAN VIEW 3: 50-MILE RADIUS SEARCH
    # ---------------------------------------------------------
    elif st.session_state.dashboard_view == "matched_requests":
        logged_in_samaritan.render_matched_requests(user_info, conn)

else:
# ---------------------------------------------------------
# LOGGED-OUT VIEW (LOGIN OR REGISTER)
# ---------------------------------------------------------
    page_action = st.radio(
        "Welcome! Please select an option:",
        options=["Login", "Register"],
        horizontal=True,
    )

    st.divider()

    # LOGIN VIEW
    if page_action == "Login":
        logged_out_login.render(conn)
    elif page_action == "Register":
        logged_out_register.render(conn)
