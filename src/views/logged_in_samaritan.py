import streamlit as st
import src.utils as utils
import pandas as pd

def render_menu():
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
    st.write("### Find Requests Near You")
    user_zip = utils.clean_zip_display(user_info.get("zip", ""))

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch requests near you.")
        all_requests_df = pd.DataFrame()

    if not all_requests_df.empty:
        all_requests_df['clean_zip'] = all_requests_df['zip'].apply(utils.clean_zip_display)
        
        available_requests = all_requests_df[
            (all_requests_df['status'].astype(str).str.lower() == 'pending') & 
            (all_requests_df['clean_zip'] == user_zip)
        ].copy()
    else:
        available_requests = pd.DataFrame()

    if available_requests.empty:
        st.info(f"No pending requests found for Zip Code: {user_zip}")
    else:
        for idx, row in available_requests.iterrows():
            with st.container():
                st.write(f"**Request:** {row['request_name']}")
                st.write(f"**Description:** {row['description']}")
                st.write(f"**Requested By:** {row['requested_by_name']}")

                if st.button("Accept Request", key=f"accept_{row['request_id']}"):
                    try:
                        req_idx = all_requests_df[all_requests_df['request_id'] == row['request_id']].index
                        if not req_idx.empty:
                            samaritan_full_name = f"{user_info['first_name']} {user_info['last_name']}".strip()
                            
                            all_requests_df.loc[req_idx, 'status'] = 'accepted'
                            all_requests_df.loc[req_idx, 'accepted_by'] = samaritan_full_name
                            all_requests_df.loc[req_idx, 'accepted_by_name'] = samaritan_full_name
                            all_requests_df.loc[req_idx, 'accepted_by_id'] = user_info['user_id']
                            
                            save_df = all_requests_df.drop(columns=['clean_zip'], errors='ignore')
                            
                            utils.safe_update_worksheet(conn, "Requests", save_df)
                            
                            # Create notification for recipient
                            recipient_id = str(row.get('requested_by_id', ''))
                            if recipient_id:
                                notif_msg = f"{samaritan_full_name} accepted your request '{row['request_name']}'!"
                                utils.create_notification(conn, recipient_id, notif_msg, str(row['request_id']))

                            st.success("Request accepted!")
                            st.rerun()
                    except Exception as e:
                        utils.handle_db_error(e, "Failed to accept request.")

            st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()

def render_accept_request(user_info, conn):
    """
    Fallback renderer when called directly from app.py line 124.
    """
    render_find_requests(user_info, conn)

def render_accepted_requests(user_info, conn):
    st.write("### Requests You're Helping With")

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
        my_accepted = all_requests_df[
            all_requests_df['accepted_by_id'].astype(str) == str(user_info["user_id"])
        ].copy()
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch accepted requests.")
        my_accepted = pd.DataFrame()

    if my_accepted.empty:
        st.info("You haven't accepted any requests yet.")
    else:
        for idx, row in my_accepted.iterrows():
            with st.container():
                st.write(f"**Request:** {row['request_name']}")
                st.write(f"**Description:** {row['description']}")
                st.write(f"**Zip Code:** {utils.clean_zip_display(row['zip'])}")
                st.write(f"**Requested By:** {row['requested_by_name']}")
                st.success("✅ Status: Accepted (In Progress)")

            st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()
