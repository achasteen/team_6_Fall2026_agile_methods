import streamlit as st
import pandas as pd
import src.ui as ui
import src.utils as utils

def _upgrade_legacy_password(conn, user_id, plain_password):
    """
    Replaces a legacy plaintext password with a bcrypt hash.
    Failures are non-fatal: the user is still logged in and migration retries next login.
    """
    try:
        users_df = utils.fetch_worksheet_cached(conn, "Users", ttl=0)
        id_mask = users_df['user_id'].astype(str).str.strip() == user_id
        if id_mask.any():
            users_df['password'] = users_df['password'].astype("object")
            users_df.loc[id_mask, 'password'] = utils.hash_password(plain_password)
            utils.safe_update_worksheet(conn, "Users", users_df)
    except Exception:
        pass

def build_session_user(user_id, row):
    """
    Builds the current_user dict from a Users row, with fallbacks for missing/NaN values.
    """
    first_name = row.get('first_name')
    last_name = row.get('last_name')
    role = row.get('role')
    user_zip = row.get('zip')

    return {
        "user_id": str(user_id).strip(),
        "first_name": str(first_name).strip() if pd.notna(first_name) and str(first_name).strip() else "User",
        "last_name": str(last_name).strip() if pd.notna(last_name) else "",
        "role": str(role).strip() if pd.notna(role) and str(role).strip() else "User",
        "zip": utils.clean_zip_display(user_zip) if pd.notna(user_zip) else "",
    }

def render(conn):
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

    try:
        with st.spinner("Checking your details..."):
            # Use short-term cached read to protect API rate limits
            user_existing_df = utils.fetch_worksheet_cached(conn, "Users")

            # Ensure user_id column is treated as string and stripped of extra spaces
            user_existing_df['user_id'] = user_existing_df['user_id'].astype(str).str.strip()
            user_match = user_existing_df[user_existing_df['user_id'] == str(login_id).strip()]

            is_valid, needs_rehash = False, False
            if not user_match.empty:
                matched_row = user_match.iloc[0].to_dict()
                is_valid, needs_rehash = utils.verify_password(
                    str(login_pass).strip(), matched_row.get('password', '')
                )

        if not is_valid:
            # Same message for unknown ID and wrong password so IDs can't be probed
            st.error("That User ID and password don't match. Check them and try again.")
            return

        if needs_rehash:
            _upgrade_legacy_password(conn, str(login_id).strip(), str(login_pass).strip())

        st.session_state.logged_in = True
        st.session_state.current_user = build_session_user(login_id, matched_row)
        ui.flash(f"Logged in as {st.session_state.current_user['first_name']}.")
        st.rerun()
    except Exception as e:
        utils.handle_db_error(e, "Could not reach the Users database.")
