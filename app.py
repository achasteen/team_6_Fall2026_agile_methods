import streamlit as st

import src.ui as ui
import src.views.logged_in_samaritan as logged_in_samaritan
import src.views.logged_in_user as logged_in_user
import src.views.logged_out_login as logged_out_login
import src.views.logged_out_register as logged_out_register
import src.views.messages as messages
import src.views.notifications as notifications

# 1. Page Configuration
st.set_page_config(
    page_title="Samaritan Services",
    page_icon=":material/volunteer_activism:",
    layout="wide",
    initial_sidebar_state="auto",
)
ui.inject_styles()

# 2. Session State Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "current_user" not in st.session_state:
    st.session_state.current_user = None

ui.show_flash()

# Dashboard views per role: view id -> nav label
USER_VIEWS = {
    "user_request_status": ":material/list_alt: My requests",
    "new_request": ":material/add: Ask for help",
}
SAMARITAN_VIEWS = {
    "sam_find_requests": ":material/travel_explore: Find requests near me",
    "sam_my_accepted": ":material/handshake: Requests I'm helping with",
}


def log_out():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.pop("dashboard_view", None)
    for key in ("pending_view", "last_view", "open_thread", "pending_thread", "sidebar_action"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------
# LOGGED IN FLOW
# ---------------------------------------------------------
if st.session_state.logged_in and st.session_state.current_user:
    user_info = st.session_state.current_user
    user_role = str(user_info.get("role", "User")).title()
    is_samaritan = user_role == "Samaritan"
    views = SAMARITAN_VIEWS if is_samaritan else USER_VIEWS

    if "pending_thread" in st.session_state:
        st.session_state.open_thread = st.session_state.pop("pending_thread")

    # Top bar
    col_brand, col_account = st.columns([1, 1], vertical_alignment="center")
    with col_brand:
        ui.wordmark()
    with col_account:
        with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
            ui.html_block(
                f'<span class="meta">{ui.esc(full_name)}</span> '
                + ui.tag("Samaritan" if is_samaritan else "Member", "blue" if is_samaritan else "gray")
            )
            unread = messages.unread_total(user_info["user_id"], st.session_state.get("open_thread"))
            st.button(
                f"Messages ({unread})" if unread else "Messages", type="tertiary",
                icon=":material/chat_bubble:", on_click=ui.open_sidebar, key="btn_mobile_messages",
            )
            st.button("Log out", type="tertiary", icon=":material/logout:", on_click=log_out, key="btn_logout")

    st.space("medium")

    # Conversations live in the sidebar; an open one replaces the dashboard
    with st.sidebar:
        messages.render_sidebar(user_info, is_samaritan)
    ui.apply_sidebar_action()

    if st.session_state.get("open_thread"):
        messages.render_thread(user_info, st.session_state.open_thread)
        st.stop()

    # Greeting
    st.title(f"Good to see you, {user_info.get('first_name', '')}.")
    if is_samaritan:
        ui.lede("Here are people near you who could use a hand. Accept a request and they'll be notified.")
    else:
        ui.lede("Ask for help with something, then check back here to see who's picked it up.")

    st.space("small")

    # Unread notifications (only shown when there is something to read)
    notifications.render_inbox(user_info["user_id"])

    # View Router: apply navigation requested by a view, then fall back to the last
    # tab used (the nav widget's state is dropped while a thread is open), then the role's default
    if "pending_view" in st.session_state:
        st.session_state.dashboard_view = st.session_state.pop("pending_view")
    if st.session_state.get("dashboard_view") not in views:
        last_view = st.session_state.get("last_view")
        st.session_state.dashboard_view = last_view if last_view in views else next(iter(views))

    st.segmented_control(
        "Navigation",
        options=list(views),
        format_func=lambda v: views[v],
        key="dashboard_view",
        required=True,
        label_visibility="collapsed",
    )
    st.space("small")

    view = st.session_state.dashboard_view
    st.session_state.last_view = view

    if view == "sam_find_requests":
        logged_in_samaritan.render_find_requests(user_info)
    elif view == "sam_my_accepted":
        logged_in_samaritan.render_accepted_requests(user_info)
    elif view == "new_request":
        logged_in_user.render_new_request(user_info)
    else:
        logged_in_user.render_user_status(user_info)

# ---------------------------------------------------------
# LOGGED OUT FLOW
# ---------------------------------------------------------
else:
    ui.wordmark()
    st.space("large")

    col_intro, col_auth = st.columns([1.1, 1], gap="large")

    with col_intro:
        st.title("Neighbors helping neighbors.")
        ui.lede("Post a request when you need a hand, or find people near you who could use one.")
        st.space("small")
        ui.html_block(
            '<div class="steps"><div class="step"><div class="step-title">Need help?</div>'
            '<div class="meta">Describe the task and your zip code. You\'ll get a note here when a Samaritan accepts it.</div></div>'
            '<div class="step"><div class="step-title">Want to help?</div>'
            '<div class="meta">Sign up as a Samaritan, browse open requests near you, and accept the ones you can take on.</div></div></div>'
        )

    with col_auth:
        with st.container(border=True, key="panel-auth"):
            auth_mode = st.segmented_control(
                "Account",
                options=["login", "register"],
                format_func=lambda m: "Log in" if m == "login" else "Create account",
                default="login",
                key="auth_mode",
                required=True,
                label_visibility="collapsed",
                width="stretch",
            )

            if auth_mode == "register":
                logged_out_register.render()
            else:
                logged_out_login.render()
