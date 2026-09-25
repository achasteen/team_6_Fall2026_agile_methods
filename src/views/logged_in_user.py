import streamlit as st
import src.utils as utils
import pandas as pd

def render_menu():
    # ---------------------------------------------------------
    # User DASHBOARD MENU
    # ---------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        if st.button("➕ Start New Request", use_container_width=True):
            st.session_state.dashboard_view = "new_request"
            st.rerun()

    with col2:
        if st.button("📋 See Status of My Requests", use_container_width=True):
            st.session_state.dashboard_view = "user_request_status"
            st.rerun()

def render_new_request(user_info, conn):
    st.write("### Start a New Request")
    req_name = st.text_input("Request Name/Title", key="nr_name")
    req_zip = st.text_input("Zip Code", value=utils.clean_zip_display(user_info.get("zip", "")), key="nr_zip")
    req_description = st.text_area("Description of Help Needed", key="nr_description")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Back to Menu"):
            st.session_state.dashboard_view = "menu"
            st.rerun()
    with col_b:
        if st.button("Submit Request"):
            if req_name and req_zip and req_description:
                try:
                    req_existing_df = conn.read(worksheet="Requests", ttl=0)
                except Exception:
                    req_existing_df = pd.DataFrame()

                request_id = utils.generate_secure_id()

                req_new_row = pd.DataFrame([{
                    "request_id": request_id,
                    "request_name": req_name,
                    "zip": utils.clean_zip_display(req_zip),
                    "description": req_description,
                    "requested_by": f"{user_info['first_name']} {user_info['last_name']}",
                    "requested_by_name": f"{user_info['first_name']} {user_info['last_name']}",
                    "requested_by_id": user_info["user_id"],
                    "status": "pending",
                    "accepted_by": None,
                    "accepted_by_name": None,
                    "accepted_by_id": None
                }])

                req_updated_df = pd.concat([req_existing_df, req_new_row], ignore_index=True)
                conn.update(worksheet="Requests", data=req_updated_df)

                st.session_state.dashboard_view = "menu"
                st.success("Request submitted successfully!")
                st.rerun()
            else:
                st.error("Please fill out all fields.")

def render_user_status(user_info, conn):
    st.write("### Status of Your Submitted Requests")

    try:
        all_requests_df = conn.read(worksheet="Requests", ttl=0)
        my_requests = all_requests_df[
            all_requests_df['requested_by_id'].astype(str) == str(user_info["user_id"])
            ].copy()
    except Exception:
        my_requests = pd.DataFrame()

    if my_requests.empty:
        st.info("You haven't submitted any requests yet.")
    else:
        for idx, row in my_requests.iterrows():
            with st.container():
                st.write(f"**Request:** {row['request_name']}")
                st.write(f"**Description:** {row['description']}")
                st.write(f"**Zip Code:** {utils.clean_zip_display(row['zip'])}")

                status = str(row['status']).title()
                if status == "Pending":
                    st.warning("⏳ Status: Pending (Waiting for a Samaritan)")
                elif status == "Accepted":
                    samaritan = row.get('accepted_by_name', 'A Samaritan')
                    st.success(f"✅ Status: Accepted by **{samaritan}**")
                else:
                    st.info(f"ℹ️ Status: {status}")

            st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()