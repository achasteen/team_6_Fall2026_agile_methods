def render_notification_inbox(user_id, conn):
    """Renders the Notification Inbox panel inside the dashboard."""
    st.write("### 🔔 Notification Inbox")

    try:
        notifs_df = conn.read(worksheet="Notifications", ttl=0)
    except Exception:
        st.warning("Could not load Notifications worksheet.")
        return

    if notifs_df.empty or "recipient_user_id" not in notifs_df.columns:
        st.info("No notifications yet.")
        return

    # Filter for current user's notifications
    user_notifs = notifs_df[notifs_df["recipient_user_id"].astype(str) == str(user_id)].copy()

    if user_notifs.empty:
        st.info("You have no notifications right now.")
        return

    user_notifs = user_notifs.sort_values(by="created_at", ascending=False)
    
    # Safe boolean check that handles strings, booleans, and numeric formats
    is_read_series = notifs_df["is_read"].astype(str).str.upper().isin(["TRUE", "1", "1.0"])
    unread_count = len(user_notifs[~user_notifs["is_read"].astype(str).str.upper().isin(["TRUE", "1", "1.0"])])

    if unread_count > 0:
        st.caption(f"You have **{unread_count} unread** notification(s).")

    for idx, row in user_notifs.iterrows():
        is_read_val = str(row["is_read"]).upper() in ["TRUE", "1", "1.0"]
        badge = "⚪ " if is_read_val else "🔴 "

        with st.container():
            col_content, col_action = st.columns([4, 1])

            with col_content:
                st.markdown(f"{badge}**{row['message']}**")
                st.caption(f"Received: {row['created_at']}")

            with col_action:
                if not is_read_val:
                    if st.button("Mark Read", key=f"read_{row['notification_id']}"):
                        # Convert column to string/object before setting to avoid dtype TypeError
                        notifs_df["is_read"] = notifs_df["is_read"].astype(str)
                        notifs_df.loc[notifs_df["notification_id"].astype(str) == str(row["notification_id"]), "is_read"] = "TRUE"
                        conn.update(worksheet="Notifications", data=notifs_df)
                        st.rerun()

        st.divider()
