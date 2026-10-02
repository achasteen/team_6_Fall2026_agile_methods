import streamlit as st
import src.ui as ui
import src.utils as utils
import pandas as pd
import math
from functools import lru_cache

RADIUS_OPTIONS = [5, 10, 25, 50, 100]

@st.cache_resource
def _zip_database():
    try:
        from pyzipcode import ZipCodeDatabase
        return ZipCodeDatabase()
    except Exception:
        return None

@lru_cache(maxsize=4096)
def _zip_coords(zip_code):
    zcdb = _zip_database()
    if zcdb is None:
        return None
    try:
        z = zcdb[zip_code]
        return float(z.latitude), float(z.longitude)
    except Exception:
        return None

def calculate_zip_distance(zip1, zip2):
    """
    Calculates distance between zip codes in miles using zip centroids.
    Falls back to a rough prefix-based estimate if a zip can't be located.
    """
    z1_str, z2_str = str(zip1).zfill(5), str(zip2).zfill(5)
    if z1_str == z2_str:
        return 0.0

    c1, c2 = _zip_coords(z1_str), _zip_coords(z2_str)
    if c1 and c2:
        lat1, lon1, lat2, lon2 = map(math.radians, [c1[0], c1[1], c2[0], c2[1]])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return 3958.8 * 2 * math.asin(math.sqrt(a))

    # Simple estimation fallback
    try:
        return abs(int(z1_str[:3]) - int(z2_str[:3])) * 12.5
    except ValueError:
        return float("inf")

def _accept_request(request_id, user_info, conn):
    """
    Re-reads the sheet so a request already taken by someone else isn't overwritten.
    Returns the accepted row, or None if it's no longer available.
    """
    all_requests_df = utils.fetch_worksheet_cached(conn, "Requests", ttl=0)
    req_idx = all_requests_df[all_requests_df['request_id'].astype(str) == str(request_id)].index
    if req_idx.empty or str(all_requests_df.loc[req_idx[0], 'status']).strip().lower() != 'pending':
        return None

    samaritan_full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
    samaritan_id = str(user_info.get('user_id', '')).strip()

    # Cast target columns to 'object' dtype so string values aren't rejected by float columns
    for col in ['status', 'accepted_by', 'accepted_by_name', 'accepted_by_id']:
        if col not in all_requests_df.columns:
            all_requests_df[col] = ""
        all_requests_df[col] = all_requests_df[col].astype("object")

    all_requests_df.loc[req_idx, 'status'] = 'accepted'
    all_requests_df.loc[req_idx, 'accepted_by'] = samaritan_full_name
    all_requests_df.loc[req_idx, 'accepted_by_name'] = samaritan_full_name
    all_requests_df.loc[req_idx, 'accepted_by_id'] = samaritan_id

    utils.safe_update_worksheet(conn, "Requests", all_requests_df)

    row = all_requests_df.loc[req_idx[0]]
    recipient_id = str(row.get('requested_by_id', '')).strip()
    if recipient_id and recipient_id.lower() != 'nan':
        notif_msg = f"{samaritan_full_name} accepted your request '{row.get('request_name', 'Request')}'."
        utils.create_notification(conn, recipient_id, notif_msg, str(request_id))
    return row

def render_find_requests(user_info, conn):
    default_zip = utils.clean_zip_display(user_info.get("zip", ""))

    col_search, col_radius = st.columns([1, 2], gap="large", vertical_alignment="bottom")
    with col_search:
        search_zip = st.text_input("Zip code", value=default_zip, max_chars=5, key="sam_search_zip_input")
        search_zip_clean = utils.clean_zip_display(search_zip)
    with col_radius:
        max_radius = st.select_slider(
            "Distance (miles)", options=RADIUS_OPTIONS, value=25, key="sam_radius_slider",
        )

    try:
        all_requests_df = utils.fetch_worksheet_cached(conn, "Requests")
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch requests.")
        all_requests_df = pd.DataFrame()

    if not all_requests_df.empty and search_zip_clean:
        all_requests_df = all_requests_df.copy()
        all_requests_df['clean_zip'] = all_requests_df['zip'].apply(utils.clean_zip_display)
        all_requests_df['distance_miles'] = all_requests_df['clean_zip'].apply(
            lambda z: calculate_zip_distance(search_zip_clean, z)
        )
        available_requests = all_requests_df[
            (all_requests_df['status'].astype(str).str.lower() == 'pending') &
            (all_requests_df['distance_miles'] <= max_radius)
        ].sort_values('distance_miles')
    else:
        available_requests = pd.DataFrame()

    st.space("small")

    if available_requests.empty:
        ui.empty_state(
            "No open requests nearby right now.",
            f"Nothing is waiting within {max_radius} miles of {search_zip_clean or 'that zip code'}. "
            "Try a wider distance, or check back later.",
        )
        return

    count = len(available_requests)
    ui.meta(f"{count} open request{'s' if count != 1 else ''} within {max_radius} miles of {search_zip_clean}, closest first.")

    for idx, row in available_requests.iterrows():
        distance = row.get('distance_miles')
        distance_label = "Same zip" if distance == 0 else f"{distance:.1f} mi"
        requester = row.get('requested_by_name', row.get('requested_by', 'A neighbor'))
        requester = requester if pd.notna(requester) and str(requester).strip() else "A neighbor"
        meta = (
            f"Posted by <strong>{ui.esc(requester)}</strong>"
            f' <span class="mono">&nbsp;{ui.esc(row.get("clean_zip"))}</span>'
        )

        with st.container(border=True, key=f"card-find-{idx}"):
            ui.request_details(row.get('request_name', 'Request'), row.get('description', ''), meta, ui.tag(distance_label, "gray"))

            if st.button("Accept request", type="primary", icon=":material/check:", key=f"accept_{row['request_id']}_{idx}"):
                try:
                    with st.spinner("Accepting..."):
                        accepted = _accept_request(row['request_id'], user_info, conn)
                except Exception as e:
                    utils.handle_db_error(e, "Failed to accept request.")
                else:
                    if accepted is None:
                        st.warning("Someone else just accepted this one. The list has been refreshed.")
                        st.cache_data.clear()
                    else:
                        ui.flash(f"You're helping with '{row.get('request_name', 'this request')}'. They've been notified.")
                        ui.go_to("sam_my_accepted")

def render_accepted_requests(user_info, conn):
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
        ui.empty_state(
            "You're not helping with anything yet.",
            "When you accept a request it will show up here, with the details you need.",
        )
        if st.button("Find requests near me", type="primary", icon=":material/travel_explore:", key="btn_empty_find"):
            ui.go_to("sam_find_requests")
        return

    count = len(my_accepted)
    ui.meta(f"You've accepted {count} request{'s' if count != 1 else ''}.")

    for idx, row in my_accepted.iloc[::-1].iterrows():
        requester = row.get('requested_by_name', row.get('requested_by', 'A neighbor'))
        requester = requester if pd.notna(requester) and str(requester).strip() else "A neighbor"
        meta = (
            f"For <strong>{ui.esc(requester)}</strong>"
            f' <span class="mono">&nbsp;{ui.esc(utils.clean_zip_display(row.get("zip", "")))}</span>'
        )
        with st.container(border=True, key=f"card-accepted-{idx}"):
            ui.request_details(row.get('request_name', 'Request'), row.get('description', ''), meta, ui.tag("In progress", "green"))
