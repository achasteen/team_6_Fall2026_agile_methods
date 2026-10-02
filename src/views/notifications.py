import streamlit as st
import src.db as db
import src.ui as ui
import src.utils as utils

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
            col_msg, col_btn = st.columns([4, 1], vertical_alignment="center")
            with col_msg:
                ui.html_block(f'<p style="margin:0">{ui.esc(notif["message"])}</p>')
            with col_btn:
                if st.button("Mark read", type="tertiary", key=f"btn_mark_read_{notif['notif_id']}"):
                    try:
                        db.mark_notification_read(notif["notif_id"], user_id)
                    except Exception as e:
                        utils.handle_db_error(e, "Could not update notification status.")
                    else:
                        st.rerun()
    st.space("small")
