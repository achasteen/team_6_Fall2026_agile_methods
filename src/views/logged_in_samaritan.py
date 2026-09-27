import streamlit as st
import src.utils as utils
import pandas as pd
import math

def calculate_zip_distance(zip1, zip2):
    """
    Calculates approximate distance (miles) between two US zip codes.
    Uses pypipcode/uszipcode if available, or falls back to standard approximate zip coordinate map.
    """
    try:
        from uszipcode import SearchEngine
        search = SearchEngine()
        z1 = search.by_zipcode(zip1)
        z2 = search.by_zipcode(zip2)
        if z1.lat and z1.lng and z2.lat and z2.lng:
            # Haversine distance
            lat1, lon1, lat2, lon2 = map(math.radians, [z1.lat, z1.lng, z2.lat, z2.lng])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            return 3958.8 * 2 * math.asin(math.sqrt(a))
    except Exception:
        pass

    # Simple fallback: exact match = 0 miles, numeric prefix proximity estimation
    z1_str, z2_str = str(zip1).zfill(5), str(zip2).zfill(5)
    if z1_str == z2_str:
        return 0.0
    
    # Prefix-based estimation fallback if distance library isn't installed
    diff = abs(int(z1_str[:3]) - int(z2_str[:3]))
    return diff * 12.5  # Rough estimation per prefix difference

def render_menu():
    """Renders the main Samaritan navigation dashboard."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Find Requests Near Me", use_container_width=True, key="btn_find_near_me"):
            st.session_state.dashboard_view = "sam_find_requests"
            st.rerun()

    with col2:
        if st.button("🤝 Requests I'm Helping With", use_container_width=True, key="btn_my_accepted"):
            st.session_state.dashboard_view = "sam_my_accepted"
            st.rerun()

def render_find_requests(user_info, conn):
    """
    Renders request search with Zip code search AND 50-mile radius filter.
    """
    st.write("### Find Requests Near You")
    
    col_search, col_radius = st.columns([2, 1])
    
    default_zip = utils.clean_zip_display(user_info.get("zip", ""))
    
    with col_search:
        search_zip = st.text_input("Search Zip Code", value=default_zip, key="sam_search_zip_input")
        search_zip_clean = utils.clean_zip_display(search_zip)

    with col_radius:
        max_radius = st.slider("Radius (Miles)", min_value=5, max_value=100, value=50, step=5, key="sam_radius_slider")

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch requests.")
        all_requests_df = pd.DataFrame()

    if not all_requests_df.empty and search_zip_clean:
        all_requests_df['clean_zip'] = all_requests_df['zip'].apply(utils.clean_zip_display)
        
        # Calculate distance for each request relative to the search Zip
        all_requests_df['distance_miles'] = all_requests_df['clean_zip'].apply(
            lambda z: calculate_zip_distance(search_zip_clean, z)
        )
        
        # Filter for pending requests within the specified radius (e.g., 50 miles)
        available_requests = all_requests_df[
            (all_requests_df['status'].astype(str).str.lower() == 'pending') & 
            (all_requests_df['distance_miles'] <= max_radius)
        ].sort_values('distance_miles').copy()
    else:
        available_requests = pd.DataFrame()

    st.write(f"#### Pending Requests within **{max_radius} miles** of **{search_zip_clean if search_zip_clean else 'N/A'}**")

    if available_requests.empty:
        st.info(f"No pending requests found within {max_radius} miles of Zip Code: {search_zip_clean}")
    else:
        for idx, row in available_requests.iterrows():
            with st.container():
                dist_str = f" ({row['distance_miles']:.1f} miles away)" if pd.notna(row.get('distance_miles')) else ""
                st.write(f"**Request:** {row.get('request_name', 'N/A')} {dist_str}")
                st.write(f"**Description:** {row.get('description', 'N/A')}")
                st.write(f"**Zip Code:** {row.get('clean_zip')}")
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
                            
                            save_df = all_requests_df.drop(columns=['clean_zip', 'distance_miles'], errors='ignore')
                            
                            utils.safe_update_worksheet(conn, "Requests", save_df)
                            
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
    render_find_requests(user_info, conn)

def render_accepted_requests(user_info, conn):
    """
    Renders the requests accepted by the Samaritan ("Requests I'm Helping With").
    """
    st.write("### Requests You're Helping With")

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
        current_user_id = str(user_info.get("user_id", "")).strip()
        current_user_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

        if not all_requests_df.empty:
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
