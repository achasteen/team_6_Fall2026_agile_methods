import re
from datetime import date, datetime

import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils
from src.views.logged_out_login import build_session_user

MIN_AGE = 18

ROLE_LABELS = {"User": "Get help", "Samaritan": "Offer help"}
ROLE_CAPTIONS = [
    "Post requests for things you need a hand with.",
    "Browse requests near you and accept the ones you can take on.",
]

def _age_on(dob, today):
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def render():
    st.subheader("Create your account")
    ui.meta("This app is for educational purposes. Please don't enter sensitive information.")

    role = st.radio(
        "I'm signing up to",
        options=["User", "Samaritan"],
        format_func=lambda r: ROLE_LABELS[r],
        captions=ROLE_CAPTIONS,
        key="account_role",
    )

    with st.form("register_form", border=False):
        reg_user_id = st.text_input("User ID", key="reg_user_id", help="You'll use this to log in.")
        reg_password = st.text_input(
            "Password", type="password", key="reg_password",
            help=f"Up to {utils.BCRYPT_MAX_BYTES} characters.",
        )
        reg_password_confirm = st.text_input("Confirm password", type="password", key="reg_password_confirm")

        col_first, col_last = st.columns(2)
        with col_first:
            first_name = st.text_input("First name", key="reg_first")
        with col_last:
            last_name = st.text_input("Last name", key="reg_last")

        st.caption("Date of birth")
        dob_str = utils.render_dob_selector("reg_dob")

        col_city, col_state, col_zip = st.columns([2, 1, 1])
        with col_city:
            city = st.text_input("City", key="reg_city")
        with col_state:
            state = st.text_input("State", key="reg_state", max_chars=2, placeholder="PA")
        with col_zip:
            zip_code = st.text_input("Zip code", key="reg_zip", max_chars=5)

        if role == "Samaritan":
            services = st.text_area(
                "Services you'd like to offer", key="reg_services",
                placeholder="Grocery runs, yard work, rides to appointments",
            )
        else:
            services = ""

        submitted = st.form_submit_button(
            "Create account", type="primary", width="stretch"
        )

    if not submitted:
        return

    reg_user_id = reg_user_id.strip()
    password = reg_password.strip()

    errors = []
    if not reg_user_id:
        errors.append("Choose a User ID.")
    if not password:
        errors.append("Choose a password.")
    elif len(password.encode("utf-8")) > utils.BCRYPT_MAX_BYTES:
        errors.append(f"Password is too long. Use at most {utils.BCRYPT_MAX_BYTES} characters.")
    elif password != reg_password_confirm.strip():
        errors.append("The passwords don't match.")
    if not first_name.strip() or not last_name.strip():
        errors.append("Enter your first and last name.")
    if not re.fullmatch(r"\d{5}", zip_code.strip()):
        errors.append("Enter a 5-digit zip code. It's used to match requests with nearby Samaritans.")

    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        if _age_on(dob, date.today()) < MIN_AGE:
            errors.append(f"You need to be at least {MIN_AGE} to sign up.")
    except ValueError:
        errors.append("That date of birth doesn't exist. Check the day and month.")

    if errors:
        for err in errors:
            st.error(err)
        return

    new_user = {
        "user_id": reg_user_id,
        "role": role,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "zip": utils.clean_zip_display(zip_code),
    }

    try:
        with st.spinner("Creating your account..."):
            created = db.create_user(
                reg_user_id, utils.hash_password(password), role,
                new_user["first_name"], new_user["last_name"], city.strip(),
                state.strip().upper(), new_user["zip"], services.strip(),
            )
    except Exception as e:
        utils.handle_db_error(e, "Could not create your account.")
        return

    if not created:
        st.error(f"The User ID '{reg_user_id}' is taken. Try another one.")
        return

    # Log the new user straight in
    st.session_state.logged_in = True
    st.session_state.current_user = build_session_user(new_user)
    ui.flash(f"Account created. Welcome, {new_user['first_name']}.")
    st.rerun()
