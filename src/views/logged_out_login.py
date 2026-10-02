import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils

def _upgrade_legacy_password(user_id, plain_password):
    """
    Replaces a legacy plaintext password with a bcrypt hash.
    Failures are non-fatal: the user is still logged in and migration retries next login.
    """
    try:
        db.set_password_hash(user_id, utils.hash_password(plain_password))
    except Exception:
        pass

def build_session_user(row):
    """
    Builds the current_user dict from a users row.
    """
    return {
        "user_id": row["user_id"],
        "first_name": (row.get("first_name") or "").strip() or "User",
        "last_name": (row.get("last_name") or "").strip(),
        "role": (row.get("role") or "").strip() or "User",
        "zip": utils.clean_zip_display(row.get("zip")),
    }

def render():
    st.subheader("Welcome back")
    ui.meta("Log in with the User ID you chose when you signed up.")

    with st.form("login_form", border=False):
        login_id = st.text_input("User ID", key="login_user_id")
        login_pass = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Log in", type="primary", width="stretch")

    if not submitted:
        return

    if not login_id or not login_pass:
        st.error("Enter both your User ID and password.")
        return

    user_id = str(login_id).strip()
    password = str(login_pass).strip()

    try:
        with st.spinner("Checking your details..."):
            user = db.get_user(user_id)
            is_valid, needs_rehash = utils.verify_password(password, user["password"]) if user else (False, False)
    except Exception as e:
        utils.handle_db_error(e, "Could not reach the database.")
        return

    if not is_valid:
        # Same message for unknown ID and wrong password so IDs can't be probed
        st.error("That User ID and password don't match. Check them and try again.")
        return

    if needs_rehash:
        _upgrade_legacy_password(user_id, password)

    st.session_state.logged_in = True
    st.session_state.current_user = build_session_user(user)
    ui.flash(f"Logged in as {st.session_state.current_user['first_name']}.")
    st.rerun()
