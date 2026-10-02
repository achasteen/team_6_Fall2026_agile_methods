import re

import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils
import src.views.messages as messages

def render_new_request(user_info):
    st.subheader("What do you need a hand with?")
    ui.meta("Samaritans near your zip code will see this and can offer to help.")

    with st.form("new_request_form", border=False, clear_on_submit=False):
        req_name = st.text_input(
            "Short title", key="nr_name", max_chars=80,
            placeholder="Groceries picked up on Thursday",
        )
        req_description = st.text_area(
            "Details", key="nr_description",
            placeholder="What needs doing, when, and anything a helper should know.",
        )
        req_zip = st.text_input(
            "Zip code", value=utils.clean_zip_display(user_info.get("zip", "")),
            key="nr_zip", max_chars=5,
        )
        submitted = st.form_submit_button("Post request", type="primary")

    if not submitted:
        return

    errors = []
    if not req_name.strip():
        errors.append("Add a short title.")
    if not req_description.strip():
        errors.append("Add a few details so a Samaritan knows what's involved.")
    if not re.fullmatch(r"\d{5}", req_zip.strip()):
        errors.append("Enter a 5-digit zip code.")
    if errors:
        for err in errors:
            st.error(err)
        return

    try:
        with st.spinner("Posting your request..."):
            full_name = f"{user_info['first_name']} {user_info['last_name']}".strip()
            db.create_request(
                req_name.strip(), req_description.strip(), utils.clean_zip_display(req_zip),
                user_info["user_id"], full_name,
            )
    except Exception as e:
        utils.handle_db_error(e, "Could not post your request.")
        return

    ui.flash("Request posted. You'll get a note here when someone accepts it.")
    ui.go_to("user_request_status")

def render_user_status(user_info):
    try:
        my_requests = db.requests_by_requester(user_info["user_id"])
    except Exception as e:
        utils.handle_db_error(e, "Could not load your requests.")
        return

    if not my_requests:
        ui.empty_state(
            "You haven't asked for help yet.",
            "Post a request and it will show up here, along with who has offered to help.",
        )
        if st.button("Ask for help", type="primary", icon=":material/add:", key="btn_empty_new_request"):
            ui.go_to("new_request")
        return

    n_pending = sum(1 for row in my_requests if row["status"] == "pending")
    n_accepted = sum(1 for row in my_requests if row["status"] == "accepted")
    ui.meta(f"{n_pending} waiting for a Samaritan, {n_accepted} accepted.")

    counts = messages.message_counts(my_requests) if n_accepted else {}
    user_id = str(user_info["user_id"]).strip()

    # Newest first
    for row in my_requests:
        status = row["status"]
        if status == "pending":
            tags = ui.tag("Waiting", "yellow")
            meta = "No one has accepted this yet."
        elif status == "accepted":
            samaritan = (row.get('accepted_by_name') or "").strip() or "A Samaritan"
            tags = ui.tag("Accepted", "green")
            meta = f"<strong>{ui.esc(samaritan)}</strong> is helping with this."
        else:
            tags = ui.tag(status.title() or "Unknown", "gray")
            meta = ""

        meta += f' <span class="mono">&nbsp;{ui.esc(utils.clean_zip_display(row.get("zip")))}</span>'

        with st.container(border=True, key=f"card-req-{row['request_id']}"):
            ui.request_details(row.get('request_name', 'Request'), row.get('description', ''), meta, tags)

            partner = messages.thread_partner(row, user_id)
            if partner:
                request_id = row['request_id']
                messages.message_button(request_id, partner[1], counts.get(request_id, 0), key=f"msg_{request_id}")
