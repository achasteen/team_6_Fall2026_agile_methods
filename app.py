import streamlit as st
from streamlit_gsheets import GSheetsConnection

import src.utils as utils
import src.views.logged_in_samaritan as logged_in_samaritan
import src.views.logged_in_user as logged_in_user
import src.views.logged_out_login as logged_out_login
import src.views.logged_out_register as logged_out_register

# 1. Page Configuration
st.set_page_config(page_title="Samaritan Services", page_icon="🤝", layout="centered")

# 2. High-Contrast White Background Card & Container CSS
st.markdown(
    """
    <style>
    /* Full-screen Background with Subtle Overlay */
    .stApp {
        background: linear-gradient(rgba(0, 0, 0, 0.25), rgba(0, 0, 0, 0.25)),
                    url("https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=1600&q=80");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    /* Solid White Card wrapping the main application content */
    [data-testid="stMainBlockContainer"] {
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        padding: 2.5rem 2rem !important;
        margin-top: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
    }

    /* Styled Expander Containers */
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 4. Session State Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "dashboard_view" not in st.session_state:
    st.session_state.dashboard_view = "menu"

# ---------------------------------------------------------
# LOGGED IN FLOW
# ---------------------------------------------------------
if st.session_state.logged_in and st.session_state.current_user:
    user_info = st.session_state.current_user
    user_role = str(user_info.get("role", "User")).title()

    st.title("Samaritan Services")
    st.write(f"### Welcome, {user_info.get('first_name', '')} {user_info.get('last_name', '')} ({user_role})")
    st.caption(f"User ID: {user_info.get('user_id')} | Zip Code: {utils.clean_zip_display(user_info.get('zip'))}")

    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.dashboard_view = "menu"
        st.rerun()

    st.divider()

    # Notification Inbox
    with st.expander("🔔 Notification Inbox", expanded=True):
        utils.render_notification_inbox(user_info["user_id"], conn)

    st.divider()

    # View Router
    view = st.session_state.get("dashboard_view", "menu")

    if user_role == "Samaritan":
        if view == "menu":
            st.subheader("Choose an Action")
            logged_in_samaritan.render_menu()
        elif view == "sam_find_requests":
            logged_in_samaritan.render_find_requests(user_info, conn)
        elif view == "sam_my_accepted":
            logged_in_samaritan.render_accepted_requests(user_info, conn)
        else:
            logged_in_samaritan.render_menu()

    else:  # Standard User
        if view == "menu":
            st.subheader("Choose an Action")
            logged_in_user.render_menu()
        elif view == "new_request":
            logged_in_user.render_new_request(user_info, conn)
        elif view == "user_request_status":
            logged_in_user.render_user_status(user_info, conn)
        else:
            logged_in_user.render_menu()

# ---------------------------------------------------------
# LOGGED OUT FLOW
# ---------------------------------------------------------
else:
    st.title("🤝 Welcome to Samaritan Services")
    
    tab_login, tab_register = st.tabs(["Log In", "Register Account"])

    with tab_login:
        logged_out_login.render(conn)

    with tab_register:
        logged_out_register.render(conn)
