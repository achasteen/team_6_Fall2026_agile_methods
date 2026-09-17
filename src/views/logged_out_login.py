import streamlit as st
import src.utils as utils

def render(conn):
    st.subheader("Login to Your Account")

    login_id = st.text_input("User ID", key="login_user_id")
    login_pass = st.text_input("Password", type="password", key="login_password")

    if st.button("Log In"):
        try:
            user_existing_df = conn.read(worksheet="Users", ttl=0)
            user_match = user_existing_df[user_existing_df['user_id'].astype(str) == str(login_id)]

            if not user_match.empty:
                stored_pass = str(user_match['password'].values[0])
                if str(login_pass) == stored_pass:
                    st.session_state.logged_in = True
                    st.session_state.current_user = {
                        "user_id": login_id,
                        "first_name": user_match['first_name'].values[0],
                        "last_name": user_match['last_name'].values[0],
                        "role": user_match['role'].values[0],
                        "zip": utils.clean_zip_display(user_match['zip'].values[0]) if 'zip' in user_match.columns else "",
                    }
                    st.rerun()
                else:
                    st.error("Incorrect Password.")
            else:
                st.error("Invalid User ID.")
        except Exception as e:
            st.error("Could not reach Users database. Please check Google Sheets setup.")