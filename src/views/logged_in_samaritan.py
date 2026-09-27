import streamlit as st
import src.utils as utils
import pandas as pd

def render_menu():
    """Renders the main Samaritan navigation dashboard."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Find Requests Near Me", use_container_width=True):
            st.session_state.dashboard_view = "sam_find_requests"
            st.rerun()

    with col2:
        if st.button("🤝 Requests I'm Helping With", use_container_width=True):
            st.session_state.dashboard_view = "sam_my_accepted"
            st.rerun()

def render_find_requests(user_info, conn):
    """
    Renders the request search view with interactive Zip code search functionality.
    """
    st.write("### Find Requests Near You")
    
    # 1. Interactive Zip Code Search Feature (Defaults to Samaritan's profile Zip)
    default_zip = utils.clean_zip_display(user_info.get("zip", ""))
    search_zip = st.text_input("Enter Zip Code to Search", value=default_zip, key="sam_search_zip_input")
    search_zip_clean = utils.clean_zip_display(search_zip)

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch requests.")
        all_requests_df = pd.DataFrame()

    if not all_requests_df.empty and search_zip_clean:
        # Standardize Zip formats for robust matching
        all_requests_df['clean_zip'] = all_requests_df['zip'].apply(utils.clean_zip_display)
        
        # Filter pending requests for the searched Zip Code
        available_requests = all_requests_df[
            (all_requests_df['status'].astype(str).str.lower() == 'pending') & 
            (all_requests_df['clean_zip'] == search_zip_clean)
        ].copy()
    else:
        available_requests = pd.DataFrame()

    st.write(f"#### Pending Requests in Zip Code: **{search_zip_clean if search_zip_clean else 'None'}**")

    if available_requests.empty:
        st.info(f"No pending requests found for Zip Code: {search_zip_clean}")
    else:
        for idx, row in available_requests.iterrows():
            with st.container():
                st.write(f"**Request:** {row.get('request_name', 'N/A')}")
                st.write(f"**Description:** {row.get('description', 'N/A')}")
                st.write(f"**Requested By:** {row.get('requested_by_name', row.get('requested_by', 'N/A'))}")

                if st.button("Accept Request", key=f"accept_{row['request_id']}"):
                    try:
                        req_idx = all_requests_df[all_requests_df['request_id'].astype(str) == str(row['request_id'])].index
                        if not req_idx.empty:
                            samaritan_full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                            samaritan_id = str(user_info.get('user_id', '')).strip()
                            
                            all_requests_df.loc[req_idx, 'status'] = 'accepted'
                            all_requests_df.loc[req_idx, 'accepted_by'] = samaritan_full_name
                            all_requests_df.loc[req_idx, 'accepted_by_name'] = samaritan_full_name
                            all_requests_df.loc[req_idx, 'accepted_by_id'] = samaritan_id
                            
                            # Clean up temporary column prior to DB write
                            save_df = all_requests_df.drop(columns=['clean_zip'], errors='ignore')
                            
                            utils.safe_update_worksheet(conn, "Requests", save_df)
                            
                            # Trigger notification to requester
                            recipient_id = str(row.get('requested_by_id', ''))
                            if recipient_id:
                                notif_msg = f"{samaritan_full_name} accepted your request '{row.get('request_name', 'Request')}'!"
                                utils.create_notification(conn, recipient_id, notif_msg, str(row['request_id']))

                            st.success("Request accepted!")
                            st.rerun()
                    except Exception as e:
                        utils.handle_db_error(e, "Failed to accept request.")

            st.divider()

    if st.button("Back to Menu", key="back_from_find"):
        st.session_state.dashboard_view = "menu"
        st.rerun()

def render_accept_request(user_info, conn):
    """Fallback router if called directly from app.py"""
    render_find_requests(user_info, conn)

def render_accepted_requests(user_info, conn):
    """
    Renders the list of requests accepted by the current Samaritan.
    """
    st.write("### Requests You're Helping With")

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
        current_user_id = str(user_info.get("user_id", "")).strip()
        current_user_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

        if not all_requests_df.empty:
            # Check matching by accepted_by_id OR accepted_by_name to catch all variations
            my_accepted = all_requests_df[
                (all_requests_df['status'].astype(str).str.lower() == 'accepted') & (
                    (all_requests_df['accepted_by_id'].astype(str).str.strip() == current_user_id) |
                    (all_requests_df['accepted_by'].astype(str).str.strip() == current_user_name) |
                    (all_requests_df['accepted_by_name'].astype(str).str.strip() == current_user_name)
                )
            ].copy()
        else:
            my_accepted = pd.DataFrame()

    except Exception as e:
        utils.handle_db_error(e, "Could not fetch accepted requests.")
        my_accepted = pd.DataFrame()

    if my_accepted.empty:
        st.info("You haven't accepted any requests yet.")
    else:
        for idx, row in my_accepted.iterrows():
            with st.container():
                st.write(f"**Request:** {row.get('request_name', 'N/A')}")
                st.write(f"**Description:** {row.get('description', 'N/A')}")
                st.write(f"**Zip Code:** {utils.clean_zip_display(row.get('zip', ''))}")
                st.write(f"**Requested By:** {row.get('requested_by_name', row.get('requested_by', 'N/A'))}")
                st.success("✅ Status: Accepted (In Progress)")

            st.divider()

    if st.button("Back to Menu", key="back_from_accepted"):
        st.session_state.dashboard_view = "menu"
        st.rerun()
