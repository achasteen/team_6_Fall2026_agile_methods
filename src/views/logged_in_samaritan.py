import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils
import src.views.messages as messages
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

def _requester_name(row):
    return (row.get("requested_by_name") or "").strip() or "A neighbor"

def render_find_requests(user_info):
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
        pending = db.pending_requests()
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch requests.")
        pending = []

    available_requests = []
    if search_zip_clean:
        for row in pending:
            row["clean_zip"] = utils.clean_zip_display(row["zip"])
            row["distance_miles"] = calculate_zip_distance(search_zip_clean, row["clean_zip"])
            if row["distance_miles"] <= max_radius:
                available_requests.append(row)
        available_requests.sort(key=lambda row: row["distance_miles"])

    st.space("small")

    if not available_requests:
        ui.empty_state(
            "No open requests nearby right now.",
            f"Nothing is waiting within {max_radius} miles of {search_zip_clean or 'that zip code'}. "
            "Try a wider distance, or check back later.",
        )
        return

    count = len(available_requests)
    ui.meta(f"{count} open request{'s' if count != 1 else ''} within {max_radius} miles of {search_zip_clean}, closest first.")

    samaritan_id = str(user_info.get("user_id", "")).strip()
    samaritan_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

    for row in available_requests:
        request_id = row["request_id"]
        distance = row["distance_miles"]
        distance_label = "Same zip" if distance == 0 else f"{distance:.1f} mi"
        meta = (
            f"Posted by <strong>{ui.esc(_requester_name(row))}</strong>"
            f' <span class="mono">&nbsp;{ui.esc(row["clean_zip"])}</span>'
        )

        with st.container(border=True, key=f"card-find-{request_id}"):
            ui.request_details(row["request_name"], row["description"], meta, ui.tag(distance_label, "gray"))

            if st.button("Accept request", type="primary", icon=":material/check:", key=f"accept_{request_id}"):
                try:
                    with st.spinner("Accepting..."):
                        accepted = db.accept_request(request_id, samaritan_id, samaritan_name)
                except Exception as e:
                    utils.handle_db_error(e, "Failed to accept request.")
                else:
                    if accepted is None:
                        st.warning("Someone else just accepted this one. Refresh to see the latest list.")
                    else:
                        ui.flash(f"You're helping with '{row['request_name']}'. They've been notified.")
                        ui.go_to("sam_my_accepted")

def render_accepted_requests(user_info):
    user_id = str(user_info.get("user_id", "")).strip()
    try:
        my_accepted = db.requests_accepted_by(user_id)
    except Exception as e:
        utils.handle_db_error(e, "Could not fetch accepted requests.")
        return

    if not my_accepted:
        ui.empty_state(
            "You're not helping with anything yet.",
            "When you accept a request it will show up here, with the details you need.",
        )
        if st.button("Find requests near me", type="primary", icon=":material/travel_explore:", key="btn_empty_find"):
            ui.go_to("sam_find_requests")
        return

    count = len(my_accepted)
    ui.meta(f"You've accepted {count} request{'s' if count != 1 else ''}.")

    counts = messages.message_counts(my_accepted)

    for row in my_accepted:
        request_id = row["request_id"]
        meta = (
            f"For <strong>{ui.esc(_requester_name(row))}</strong>"
            f' <span class="mono">&nbsp;{ui.esc(utils.clean_zip_display(row["zip"]))}</span>'
        )
        with st.container(border=True, key=f"card-accepted-{request_id}"):
            ui.request_details(row["request_name"], row["description"], meta, ui.tag("In progress", "green"))

            partner = messages.thread_partner(row, user_id)
            if partner:
                messages.message_button(request_id, partner[1], counts.get(request_id, 0), key=f"msg_{request_id}")
