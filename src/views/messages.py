from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import src.ui as ui
import src.utils as utils

MESSAGE_COLUMNS = ["message_id", "request_id", "sender_id", "sender_name", "recipient_id", "body", "sent_at"]
MESSAGE_MAX_CHARS = 1000
REFRESH_SECONDS = 15
NEW_MESSAGE_PREFIX = "New message from"

def _clean(value):
    """
    Normalizes a sheet cell to a string (blank for NaN, no trailing .0 on whole numbers).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def _display_body(body):
    # Undo the formula-injection guard added by utils.sanitize_for_csv
    if body.startswith("'") and body[1:2] in ("=", "+", "-", "@", "\t", "\r"):
        return body[1:]
    return body

def _relative_time(sent_at):
    try:
        sent = datetime.fromisoformat(sent_at)
    except ValueError:
        return ""
    seconds = (datetime.now(timezone.utc) - sent).total_seconds()
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hr ago"
    days = int(seconds // 86400)
    return "Yesterday" if days == 1 else f"{days} days ago"

def load_messages(conn, ttl=10):
    """
    Returns all messages as a DataFrame of clean strings (empty if the sheet doesn't exist yet).
    """
    try:
        df = utils.fetch_worksheet_cached(conn, "Messages", ttl=ttl)
    except Exception:
        return pd.DataFrame(columns=MESSAGE_COLUMNS)
    if df is None or df.empty:
        return pd.DataFrame(columns=MESSAGE_COLUMNS)

    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    for col in MESSAGE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].map(_clean)
    return df[df["message_id"] != ""]

def message_counts(conn):
    """
    Returns {request_id: number of messages} for showing counts on request cards.
    """
    df = load_messages(conn, ttl=15)
    return df.groupby("request_id").size().to_dict() if not df.empty else {}

def thread_partner(request_row, user_id):
    """
    Returns (partner_id, partner_name) if user_id is the requester or the accepting Samaritan
    of an accepted request, otherwise None.
    """
    if _clean(request_row.get("status")).lower() != "accepted":
        return None
    requester_id = _clean(request_row.get("requested_by_id"))
    samaritan_id = _clean(request_row.get("accepted_by_id"))
    if user_id == requester_id and samaritan_id:
        return samaritan_id, _clean(request_row.get("accepted_by_name")) or "your Samaritan"
    if user_id == samaritan_id and requester_id:
        return requester_id, _clean(request_row.get("requested_by_name")) or "the requester"
    return None

def message_button(request_id, partner_name, count, key):
    """
    Renders the 'Message <name>' button on a request card. Clicking opens the thread.
    """
    first_name = partner_name.split()[0] if partner_name else "them"
    label = f"Message {first_name}" + (f" ({count})" if count else "")
    if st.button(label, icon=":material/chat_bubble:", key=key):
        ui.open_thread(request_id)

def _notify_once(conn, recipient_id, sender_name, request_id, request_name):
    """
    Sends a 'new message' notification unless one for this thread is still unread.
    """
    try:
        notif_df = utils.fetch_worksheet_cached(conn, "Notifications", ttl=0)
        if notif_df is not None and not notif_df.empty:
            pending = notif_df[
                (notif_df["recipient_id"].map(_clean) == recipient_id) &
                (notif_df["request_id"].map(_clean) == request_id) &
                (notif_df["message"].astype(str).str.startswith(NEW_MESSAGE_PREFIX)) &
                (notif_df["is_read"].map(_clean).str.upper() != "TRUE")
            ]
            if not pending.empty:
                return
    except Exception:
        pass
    utils.create_notification(
        conn, recipient_id, f"{NEW_MESSAGE_PREFIX} {sender_name} about '{request_name}'.", request_id
    )

def _render_bubble(row, user_id):
    mine = row["sender_id"] == user_id
    who = "You" if mine else row["sender_name"]
    when = _relative_time(row["sent_at"])
    ui.html_block(
        f'<div class="msg {"msg-mine" if mine else "msg-theirs"}">'
        f'<div class="msg-bubble">{ui.esc(_display_body(row["body"]))}</div>'
        f'<div class="msg-meta">{ui.esc(who)}{" &middot; " + ui.esc(when) if when else ""}</div>'
        '</div>'
    )

def render_thread(user_info, conn, request_id):
    user_id = str(user_info.get("user_id", "")).strip()

    st.button("Back", icon=":material/arrow_back:", type="tertiary", on_click=ui.close_thread, key="btn_thread_back")

    try:
        requests_df = utils.fetch_worksheet_cached(conn, "Requests")
        match = requests_df[requests_df["request_id"].map(_clean) == str(request_id)]
    except Exception as e:
        utils.handle_db_error(e, "Could not load this conversation.")
        return

    partner = thread_partner(match.iloc[0].to_dict(), user_id) if not match.empty else None
    if partner is None:
        ui.empty_state(
            "This conversation isn't available.",
            "Messages open once a Samaritan accepts a request, and only the two of you can see them.",
        )
        return

    request_row = match.iloc[0]
    partner_id, partner_name = partner
    request_name = _clean(request_row.get("request_name")) or "Request"

    st.title(request_name)
    ui.meta(f"Conversation with {partner_name}. Only the two of you can see these messages.")
    st.space("small")

    @st.fragment(run_every=REFRESH_SECONDS)
    def _thread_messages():
        messages_df = load_messages(conn)
        thread = messages_df[messages_df["request_id"] == str(request_id)]
        if thread.empty:
            ui.empty_state(
                "No messages yet.",
                f"Say hello and sort out the details with {partner_name.split()[0]}: timing, address, anything they should bring.",
            )
            return
        thread = thread.sort_values("sent_at", kind="stable")
        for _, row in thread.iterrows():
            _render_bubble(row, user_id)

    _thread_messages()

    body = st.chat_input(f"Message {partner_name.split()[0]}", max_chars=MESSAGE_MAX_CHARS, key="chat_input_thread")
    if body and body.strip():
        sender_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        try:
            utils.append_row(conn, "Messages", {
                "message_id": utils.generate_secure_id("msg"),
                "request_id": str(request_id),
                "sender_id": user_id,
                "sender_name": sender_name,
                "recipient_id": partner_id,
                "body": body.strip(),
                "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }, MESSAGE_COLUMNS)
            _notify_once(conn, partner_id, sender_name, str(request_id), request_name)
        except Exception as e:
            utils.handle_db_error(e, "Your message wasn't sent.")
            return
        st.rerun()
