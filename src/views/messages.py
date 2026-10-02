from datetime import datetime, timezone

import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils
from src.views.notifications import NEW_MESSAGE_PREFIX

MESSAGE_MAX_CHARS = 1000
REFRESH_SECONDS = 15

def _display_body(body):
    # Messages migrated from Google Sheets may carry its formula-injection guard
    if body.startswith("'") and body[1:2] in ("=", "+", "-", "@", "\t", "\r"):
        return body[1:]
    return body

def _relative_time(sent_at):
    if sent_at is None:
        return ""
    seconds = (datetime.now(timezone.utc) - sent_at).total_seconds()
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hr ago"
    days = int(seconds // 86400)
    return "Yesterday" if days == 1 else f"{days} days ago"

def message_counts(request_rows):
    """
    Returns {request_id: number of messages} for showing counts on request cards.
    """
    try:
        return db.message_counts([row["request_id"] for row in request_rows])
    except Exception:
        return {}

def thread_partner(request_row, user_id):
    """
    Returns (partner_id, partner_name) if user_id is the requester or the accepting Samaritan
    of an accepted request, otherwise None.
    """
    if (request_row.get("status") or "").lower() != "accepted":
        return None
    requester_id = request_row.get("requested_by_id") or ""
    samaritan_id = request_row.get("accepted_by_id") or ""
    if user_id == requester_id and samaritan_id:
        return samaritan_id, request_row.get("accepted_by_name") or "your Samaritan"
    if user_id == samaritan_id and requester_id:
        return requester_id, request_row.get("requested_by_name") or "the requester"
    return None

def message_button(request_id, partner_name, count, key):
    """
    Renders the 'Message <name>' button on a request card. Clicking opens the thread.
    """
    first_name = partner_name.split()[0] if partner_name else "them"
    label = f"Message {first_name}" + (f" ({count})" if count else "")
    if st.button(label, icon=":material/chat_bubble:", key=key):
        ui.open_thread(request_id)

def _render_bubble(message, user_id):
    mine = message["sender_id"] == user_id
    who = "You" if mine else message["sender_name"]
    when = _relative_time(message["sent_at"])
    ui.html_block(
        f'<div class="msg {"msg-mine" if mine else "msg-theirs"}">'
        f'<div class="msg-bubble">{ui.esc(_display_body(message["body"]))}</div>'
        f'<div class="msg-meta">{ui.esc(who)}{" &middot; " + ui.esc(when) if when else ""}</div>'
        '</div>'
    )

def render_thread(user_info, request_id):
    user_id = str(user_info.get("user_id", "")).strip()

    st.button("Back", icon=":material/arrow_back:", type="tertiary", on_click=ui.close_thread, key="btn_thread_back")

    try:
        request_row = db.get_request(request_id)
    except Exception as e:
        utils.handle_db_error(e, "Could not load this conversation.")
        return

    partner = thread_partner(request_row, user_id) if request_row else None
    if partner is None:
        ui.empty_state(
            "This conversation isn't available.",
            "Messages open once a Samaritan accepts a request, and only the two of you can see them.",
        )
        return

    partner_id, partner_name = partner
    partner_first = partner_name.split()[0]
    request_name = request_row.get("request_name") or "Request"

    st.title(request_name)
    ui.meta(f"Conversation with {partner_name}. Only the two of you can see these messages.")
    st.space("small")

    @st.fragment(run_every=REFRESH_SECONDS)
    def _thread_messages():
        try:
            thread = db.thread_messages(request_id)
        except Exception as e:
            utils.handle_db_error(e, "Could not load messages.")
            return
        if not thread:
            ui.empty_state(
                "No messages yet.",
                f"Say hello and sort out the details with {partner_first}: timing, address, anything they should bring.",
            )
            return
        for message in thread:
            _render_bubble(message, user_id)

    _thread_messages()

    body = st.chat_input(f"Message {partner_first}", max_chars=MESSAGE_MAX_CHARS, key="chat_input_thread")
    if body and body.strip():
        sender_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        try:
            db.send_message(
                request_id, user_id, sender_name, partner_id, body.strip(),
                notification=f"{NEW_MESSAGE_PREFIX} {sender_name} about '{request_name}'.",
                notification_prefix=NEW_MESSAGE_PREFIX,
            )
        except Exception as e:
            utils.handle_db_error(e, "Your message wasn't sent.")
            return
        st.rerun()
