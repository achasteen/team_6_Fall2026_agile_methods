import streamlit as st
import pandas as pd
import src.utils as utils

def render_menu():
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🤝 Accept New Request", use_container_width=True):
            st.session_state.dashboard_view = "accept_request"
            st.rerun()

    with col2:
        if st.button("✅ See Accepted Requests", use_container_width=True):
            st.session_state.dashboard_view = "my_accepted_requests"
            st.rerun()

    with col3:
        if st.button("📍 50-Mile Radius Search", use_container_width=True):
            st.session_state.dashboard_view = "matched_requests"
            st.rerun()

def render_accept_request(user_info, conn):
    st.write("### Accept Pending Requests")

    try:
        all_requests_df = conn.read(worksheet="Requests", ttl=0)
        pending_requests = all_requests_df[all_requests_df['status'] == "pending"].copy()
    except Exception:
        pending_requests = pd.DataFrame()

    if pending_requests.empty:
        st.info("No open requests right now.")
    else:
        for idx, row in pending_requests.iterrows():
            with st.container():
                st.write(f"**Request:** {row['request_name']}")
                st.write(f"**Requested By:** {row['requested_by_name']}")
                st.write(f"**Zip Code:** {utils.clean_zip_display(row['zip'])}")
                st.write(f"**Description:** {row['description']}")

                if st.button("Accept Request", key=f"accept_open_{row['request_id']}"):
                    samaritan_name = f"{user_info['first_name']} {user_info['last_name']}"
                    req_title = row['request_name']

                    all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'status'] = 'accepted'
                    all_requests_df.loc[
                        all_requests_df['request_id'] == row['request_id'], 'accepted_by_name'] = samaritan_name
                    all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'accepted_by_id'] = \
                    user_info['user_id']
                    conn.update(worksheet="Requests", data=all_requests_df)

                    utils.create_notification(
                        recipient_id=row['requested_by_id'],
                        message=f"Your request '{req_title}' was accepted by Samaritan {samaritan_name}!",
                        notif_type="request_accepted"
                    )
                    utils.create_notification(
                        recipient_id=user_info['user_id'],
                        message=f"You successfully accepted '{req_title}'.",
                        notif_type="accepted_confirmation"
                    )

                    utils.send_browser_push("Request Accepted!", f"You accepted '{req_title}'")
                    st.success("Request accepted!")
                    st.rerun()

            st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()

def render_accepted_requests(user_info, conn):
    st.write("### Requests You've Accepted")

    try:
        all_requests_df = conn.read(worksheet="Requests", ttl=0)
        my_accepted = all_requests_df[
            (all_requests_df['accepted_by_id'].astype(str) == str(user_info["user_id"])) &
            (all_requests_df['status'] == "accepted")
            ].copy()
    except Exception:
        my_accepted = pd.DataFrame()

    if my_accepted.empty:
        st.info("You have not accepted any active requests yet.")
    else:
        for idx, row in my_accepted.iterrows():
            with st.container():
                st.write(f"**Request:** {row['request_name']}")
                st.write(f"**User:** {row['requested_by_name']}")
                st.write(f"**Zip Code:** {utils.clean_zip_display(row['zip'])}")
                st.write(f"**Description:** {row['description']}")

                if st.button("Mark Completed", key=f"complete_{row['request_id']}"):
                    all_requests_df.loc[all_requests_df['request_id'] == row['request_id'], 'status'] = 'completed'
                    conn.update(worksheet="Requests", data=all_requests_df)

                    utils.create_notification(
                        recipient_id=row['requested_by_id'],
                        message=f"Your request '{row['request_name']}' was marked completed by Samaritan {user_info['first_name']}.",
                        notif_type="request_completed"
                    )

                    st.success("Request marked as completed!")
                    st.rerun()

            st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()

def render_matched_requests(user_info, conn):
    st.write("### 📍 Requests Within 50 Miles")

    user_zip = utils.clean_zip_display(user_info.get("zip", ""))

    col_zip, col_rad = st.columns([2, 1])
    with col_zip:
        search_zip = st.text_input("Center Zip Code", value=user_zip, key="radius_zip_input")
    with col_rad:
        max_distance = st.slider("Max Miles", min_value=1, max_value=50, value=50, step=1)

    try:
        all_requests_df = conn.read(worksheet="Requests", ttl=0)
        pending_df = all_requests_df[all_requests_df['status'] == "pending"].copy()
    except Exception:
        pending_df = pd.DataFrame()

    clean_search_zip = utils.clean_zip_display(search_zip)

    if pending_df.empty or not clean_search_zip:
        st.info("No pending requests available to search.")
    else:
        nearby_requests = []
        for idx, row in pending_df.iterrows():
            dist = utils.get_zip_distance(clean_search_zip, row['zip'])
            if dist is not None and dist <= max_distance:
                row_dict = row.to_dict()
                row_dict['distance_miles'] = dist
                nearby_requests.append(row_dict)

        if not nearby_requests:
            st.warning(f"No pending requests found within **{max_distance} miles** of zip **{clean_search_zip}**.")
        else:
            st.success(f"Found **{len(nearby_requests)}** request(s) within **{max_distance} miles**:")

            nearby_requests.sort(key=lambda x: x['distance_miles'])

            for req in nearby_requests:
                with st.container():
                    st.write(f"**Request:** {req['request_name']}")
                    st.write(f"**Requested By:** {req['requested_by_name']}")
                    st.write(
                        f"**Location:** Zip {utils.clean_zip_display(req['zip'])} (**{req['distance_miles']} miles away**)")
                    st.write(f"**Description:** {req['description']}")

                    if st.button("Accept Request", key=f"accept_rad_{req['request_id']}"):
                        samaritan_name = f"{user_info['first_name']} {user_info['last_name']}"
                        req_title = req['request_name']

                        all_requests_df.loc[all_requests_df['request_id'] == req['request_id'], 'status'] = 'accepted'
                        all_requests_df.loc[
                            all_requests_df['request_id'] == req['request_id'], 'accepted_by_name'] = samaritan_name
                        all_requests_df.loc[all_requests_df['request_id'] == req['request_id'], 'accepted_by_id'] = \
                        user_info['user_id']
                        conn.update(worksheet="Requests", data=all_requests_df)

                        utils.create_notification(
                            recipient_id=req['requested_by_id'],
                            message=f"Your request '{req_title}' was accepted by Samaritan {samaritan_name}!",
                            notif_type="request_accepted"
                        )
                        utils.create_notification(
                            recipient_id=user_info['user_id'],
                            message=f"You accepted '{req_title}' posted by {req['requested_by_name']}.",
                            notif_type="accepted_confirmation"
                        )

                        utils.send_browser_push("Request Accepted!", f"You accepted '{req_title}'")
                        st.success("Request accepted!")
                        st.rerun()

                st.divider()

    if st.button("Back to Menu"):
        st.session_state.dashboard_view = "menu"
        st.rerun()