import time
import random
import streamlit as st
import pandas as pd

def clean_zip_display(zip_val):
    """
    Cleans and formats zip codes for consistent display.
    """
    if pd.isna(zip_val) or zip_val == "":
        return ""
    
    zip_str = str(zip_val).strip()
    if zip_str.endswith(".0"):
        zip_str = zip_str[:-2]
        
    return zip_str.zfill(5) if len(zip_str) < 5 and zip_str.isdigit() else zip_str

def generate_secure_id():
    """
    Generates a random unique identifier for requests or users.
    """
    import uuid
    return str(uuid.uuid4())[:8]

def render_dob_selector(key_prefix="dob"):
    """
    Renders date-of-birth input widgets and returns formatted string.
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        month = st.selectbox("DOB Month", range(1, 13), key=f"{key_prefix}_month")
    with col2:
        day = st.selectbox("DOB Day", range(1, 32), key=f"{key_prefix}_day")
    with col3:
        year = st.selectbox("DOB Year", range(1900, 2027), index=100, key=f"{key_prefix}_year")
    return f"{year:04d}-{month:02d}-{day:02d}"

# ---------------------------------------------------------
# RATE-LIMITING & API QUOTA PROTECTION
# ---------------------------------------------------------

def retry_api_call(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator that retries a function if it encounters API quota/rate limit errors (HTTP 429/503).
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    err_msg = str(e).lower()
                    if any(indicator in err_msg for indicator in ["429", "quota", "resource_exhausted", "503"]):
                        if attempt == max_retries:
                            st.error("⚠️ Database is temporarily busy due to high traffic. Please try again in a few seconds.")
                            raise e
                        sleep_time = delay + random.uniform(0, 0.5)
                        time.sleep(sleep_time)
                        delay *= backoff_factor
                    else:
                        raise e
        return wrapper
    return decorator

@st.cache_data(ttl=15, show_spinner=False)
def fetch_worksheet_cached(_conn, worksheet_name: str) -> pd.DataFrame:
    """
    Fetches worksheet data with short term caching (15s) to prevent API rate-limiting.
    _conn is prefixed with '_' so Streamlit doesn't hash the unhashable connection object.
    """
    try:
        return _conn.read(worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.warning(f"Unable to refresh data for '{worksheet_name}'. Showing cached data if available.")
        raise e

@retry_api_call(max_retries=3, initial_delay=1.0)
def safe_update_worksheet(conn, worksheet_name: str, data: pd.DataFrame):
    """
    Safely updates worksheet data with exponential backoff and invalidates cache upon success.
    """
    conn.update(worksheet=worksheet_name, data=data)
    fetch_worksheet_cached.clear()
