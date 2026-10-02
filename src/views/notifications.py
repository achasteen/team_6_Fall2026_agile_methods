import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils

NEW_MESSAGE_PREFIX = "New message from"

def render_inbox(user_id):
    """
    Renders the user's unread notifications. Shows nothing when there are none.
    """
    try:
        unread = db.unread_notifications(user_id)
    except Exception:
        return

    if not unread:
        return

    with st.container(border=True, key="panel-notifications"):
        ui.html_block(
            '<p class="card-title" style="margin:0 0 0.25rem">Updates '
            f'{ui.tag(f"{len(unread)} new", "blue")}</p>'
        )
        for notif in unread:
            notif_id = notif["notif_id"]
            request_id = notif.get("request_id")
            is_message = notif["message"].startswith(NEW_MESSAGE_PREFIX)
            col_msg, col_btn = st.columns([3, 1], vertical_alignment="center")

            with col_msg:
                ui.html_block(f'<p style="margin:0">{ui.esc(notif["message"])}</p>')

            with col_btn:
                with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
                    open_clicked = bool(is_message and request_id) and st.button(
                        "Open", type="tertiary", key=f"btn_open_{notif_id}"
                    )
                    read_clicked = st.button("Mark read", type="tertiary", key=f"btn_mark_read_{notif_id}")

            if open_clicked or read_clicked:
                try:
                    db.mark_notification_read(notif_id, user_id)
                except Exception as e:
                    utils.handle_db_error(e, "Could not update notification status.")
                else:
                    if open_clicked:
                        ui.open_thread(request_id)
                    st.rerun()
    st.space("small")
