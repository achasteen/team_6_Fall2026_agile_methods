import streamlit as st
import pandas as pd
import uuid
import hmac
import bcrypt
from datetime import datetime

# bcrypt only uses the first 72 bytes of input; longer passwords are rejected
BCRYPT_MAX_BYTES = 72
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

def hash_password(plain_password):
    """
    Hashes a plaintext password with bcrypt (salted). Returns the hash as a string.
    """
    return bcrypt.hashpw(str(plain_password).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def is_bcrypt_hash(value):
    """
    Returns True if the value looks like a bcrypt hash.
    """
    return isinstance(value, str) and value.startswith(BCRYPT_PREFIXES)

def verify_password(plain_password, stored_value):
    """
    Checks a plaintext password against the stored value.
    Supports legacy plaintext records so they can be migrated on next login.
    Returns (is_valid, needs_rehash).
    """
    if pd.isna(stored_value):
        return False, False
    stored = str(stored_value).strip()
    candidate = str(plain_password).encode("utf-8")

    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(candidate, stored.encode("utf-8")), False
        except ValueError:
            return False, False

    # Legacy plaintext record: constant-time comparison, flag for upgrade
    if not stored:
        return False, False
    is_valid = hmac.compare_digest(candidate, stored.encode("utf-8"))
    return is_valid, is_valid

def generate_secure_id(prefix=""):
    """
    Generates a unique short ID string.
    """
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{unique_id}" if prefix else unique_id

def clean_zip_display(zip_val):
    """
    Cleans and formats zip codes to 5-digit strings.
    """
    if pd.isna(zip_val) or not zip_val:
        return ""
    try:
        val_str = str(zip_val).split('.')[0].strip()
        return val_str.zfill(5)
    except Exception:
        return str(zip_val)

def handle_db_error(e, fallback_msg):
    """
    Renders a user-friendly error message for database failures.
    """
    err_str = str(e)
    if "could not connect" in err_str.lower() or "timeout" in err_str.lower():
        st.warning("We couldn't reach the database. Wait a few seconds and try again.", icon=":material/cloud_off:")
    else:
        st.error(f"{fallback_msg} Please try again in a moment.")
        st.caption(f"Details: {err_str[:120]}...")  # Truncates long raw traces

def render_dob_selector(key_prefix="dob"):
    """
    Renders standard dropdowns for Date of Birth selection (Month, Day, Year).
    """
    col_m, col_d, col_y = st.columns(3)
    
    months = [
        "January", "February", "March", "April", "May", "June", 
        "July", "August", "September", "October", "November", "December"
    ]
    current_year = datetime.now().year
    years = list(range(current_year - 100, current_year + 1))[::-1]
    
    with col_m:
        month = st.selectbox("Month", options=months, key=f"{key_prefix}_month")
    with col_d:
        day = st.selectbox("Day", options=list(range(1, 32)), key=f"{key_prefix}_day")
    with col_y:
        year = st.selectbox("Year", options=years, key=f"{key_prefix}_year")

    month_num = months.index(month) + 1
    return f"{year:04d}-{month_num:02d}-{day:02d}"
