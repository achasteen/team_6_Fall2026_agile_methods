import streamlit as st
import src.utils as utils
import src.views.logged_in_samaritan as logged_in_samaritan
# ... import other views as needed ...

# Initialize connection and session state
conn = st.connection("gsheets", type=GSheetsConnection)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "dashboard_view" not in st.session_state:
    st.session_state.dashboard_view = "menu"

if st.session_state.logged_in:
    user_info = st.session_state.current_user
    
    st.title("Samaritan Services")
    st.write(f"### Welcome, {user_info.get('first_name', '')} {user_info.get('last_name', '')} ({user_info.get('role', 'User')})")
    st.caption(f"User ID: {user_info.get('user_id')} | Zip Code: {user_info.get('zip')}")
    
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.dashboard_view = "menu"
        st.rerun()

    # Notification Inbox
    with st.expander("🔔 Notification Inbox", expanded=True):
        utils.render_notification_inbox(user_info["user_id"], conn)

    st.divider()

    # ROUTING LOGIC BASED ON SESSION STATE
    view = st.session_state.get("dashboard_view", "menu")

    if view == "menu":
        st.subheader("Choose an Action")
        logged_in_samaritan.render_menu()
    elif view == "sam_find_requests":
        logged_in_samaritan.render_find_requests(user_info, conn)
    elif view == "sam_my_accepted":
        logged_in_samaritan.render_accepted_requests(user_info, conn)
    else:
        logged_in_samaritan.render_menu()
