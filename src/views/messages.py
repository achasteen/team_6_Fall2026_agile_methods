from datetime import datetime, timezone

import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils

MESSAGE_MAX_CHARS = 1000
REFRESH_SECONDS = 15

def _seconds_ago(timestamp):
    return (datetime.now(timezone.utc) - timestamp).total_seconds()

def _relative_time(sent_at):
    seconds = _seconds_ago(sent_at)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hr ago"
    days = int(seconds // 86400)
    return "Yesterday" if days == 1 else f"{days} days ago"

def _short_time(sent_at):
    if sent_at is None:
        return ""
    seconds = _seconds_ago(sent_at)
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    if seconds < 7 * 86400:
        return f"{int(seconds // 86400)}d"
    return f"{sent_at:%b} {sent_at.day}"

def _full_name(user_info):
    return f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

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

def message_button(request_id, partner_name, key):
    """
    Renders the 'Message <name>' button on a request card. Clicking opens the conversation.
    """
    first_name = partner_name.split()[0] if partner_name else "them"
    if st.button(f"Message {first_name}", icon=":material/chat_bubble:", key=key):
        ui.open_thread(request_id)

def unread_total(user_id, open_request_id=None):
    """
    Unread messages across all conversations, not counting the one currently open.
    """
    try:
        return db.unread_message_count(user_id, except_request_id=open_request_id)
    except Exception:
        return 0

# ---------------------------------------------------------
# SIDEBAR INBOX
# ---------------------------------------------------------
def _conversation_row(convo, user_id, is_open):
    request_id = convo["request_id"]
    partner_name = convo["partner_name"] or "Neighbor"
    unread = 0 if is_open else convo["unread"]

    if convo["last_sender_id"] == user_id:
        preview = f"You: {convo['last_body']}"
    else:
        preview = convo["last_body"]

    classes = "dm-row" + (" dm-open" if is_open else "") + (" dm-has-unread" if unread else "")
    with st.container(key=f"dmrow-{request_id}"):
        ui.html_block(
            f'<div class="{classes}">'
            f'<div class="dm-avatar">{ui.esc(partner_name[:1].upper())}</div>'
            '<div class="dm-main">'
            f'<div class="dm-top"><span class="dm-name">{ui.esc(partner_name)}</span>'
            f'<span class="dm-time">{ui.esc(_short_time(convo["last_sent_at"]))}</span></div>'
            f'<div class="dm-request">{ui.esc(convo["request_name"])}</div>'
            f'<div class="dm-preview">{ui.esc(preview)}</div>'
            '</div>'
            + (f'<span class="dm-unread">{unread}</span>' if unread else "")
            + '</div>'
        )
        # Invisible button stretched over the whole row (see .st-key-dmrow-* in ui.py)
        if st.button(f"Open conversation with {partner_name}", key=f"dm_open_{request_id}"):
            ui.open_thread(request_id)

def render_sidebar(user_info, is_samaritan):
    """
    Renders the conversation list in the sidebar. Refreshes itself every REFRESH_SECONDS.
    """
    user_id = str(user_info.get("user_id", "")).strip()

    @st.fragment(run_every=REFRESH_SECONDS)
    def _inbox():
        try:
            convos = db.conversations(user_id)
        except Exception:
            st.caption("Messages are unavailable right now.")
            return

        open_thread = st.session_state.get("open_thread")
        unread_total = sum(c["unread"] for c in convos if c["request_id"] != open_thread)
        ui.html_block(
            '<p class="dm-heading">Messages'
            + (f' {ui.tag(f"{unread_total} new", "blue")}' if unread_total else "")
            + '</p>'
        )

        if not convos:
            hint = (
                "No conversations yet. Use \"Message\" on a request you're helping with to start one."
                if is_samaritan else
                "No conversations yet. Once a Samaritan accepts your request, use \"Message\" on it to start one."
            )
            ui.html_block(f'<p class="meta">{ui.esc(hint)}</p>')
            return

        for convo in convos:
            _conversation_row(convo, user_id, convo["request_id"] == open_thread)

    _inbox()

# ---------------------------------------------------------
# CONVERSATION (main area)
# ---------------------------------------------------------
def _render_bubble(message, user_id):
    mine = message["sender_id"] == user_id
    who = "You" if mine else message["sender_name"]
    when = _relative_time(message["sent_at"])
    ui.html_block(
        f'<div class="msg {"msg-mine" if mine else "msg-theirs"}">'
        f'<div class="msg-bubble">{ui.esc(message["body"])}</div>'
        f'<div class="msg-meta">{ui.esc(who)} &middot; {ui.esc(when)}</div>'
        '</div>'
    )

def _send(request_id, user_info, partner_id, input_key):
    body = (st.session_state.get(input_key) or "").strip()
    if not body:
        return
    try:
        db.send_message(request_id, str(user_info["user_id"]).strip(), _full_name(user_info), partner_id, body)
    except Exception as e:
        st.session_state.send_error = str(e)

def render_thread(user_info, request_id):
    user_id = str(user_info.get("user_id", "")).strip()

    st.button("Close", icon=":material/close:", type="tertiary", on_click=ui.close_thread, key="btn_thread_back")

    try:
        request_row = db.get_request_for_user(request_id, user_id)
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

    st.title(partner_name)
    ui.meta(f"About '{request_row.get('request_name') or 'Request'}'. Only the two of you can see these messages.")
    st.space("small")

    if "send_error" in st.session_state:
        utils.handle_db_error(Exception(st.session_state.pop("send_error")), "Your message wasn't sent.")

    @st.fragment(run_every=REFRESH_SECONDS)
    def _thread_messages():
        try:
            thread = db.thread_messages_for_user(request_id, user_id)
            if any(m["recipient_id"] == user_id and m["read_at"] is None for m in thread):
                db.mark_thread_read(request_id, user_id)
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

    input_key = f"chat_input_{request_id}"
    st.chat_input(
        f"Message {partner_first}", max_chars=MESSAGE_MAX_CHARS, key=input_key,
        on_submit=_send, args=(request_id, user_info, partner_id, input_key),
    )
