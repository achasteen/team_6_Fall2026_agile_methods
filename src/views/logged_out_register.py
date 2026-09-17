import streamlit as st
import src.utils as utils
import pandas as pd

def render(conn):
    st.subheader("Account Registration")
    st.caption("Please fill out the information below to create your profile.")

    role = st.selectbox("I am registering as a:", options=["User", "Samaritan"], key="account_role")

    reg_user_id = st.text_input("User ID", key="reg_user_id")
    reg_password = st.text_input("Password", type="password", key="reg_password")

    first_name = st.text_input("First Name", key="reg_first")
    # middle_name = st.text_input("Middle Name or Initial", key="reg_middle")
    last_name = st.text_input("Last Name", key="reg_last")

    dob_str = utils.render_dob_selector("reg_dob")

    city = st.text_input("City", key="reg_city")
    state = st.text_input("State", key="reg_state")
    zip_code = st.text_input("Zip Code", key="reg_zip")
    age = st.number_input("Age", min_value=18, max_value=120, key="reg_age")

    if role == "Samaritan":
        services = st.text_area("Services you would like to offer", key="reg_services")
        # uploaded_file = st.file_uploader("Upload a picture of driver's license", type=["jpeg", "jpg", "png"],
        #                                  key="reg_dl_pic")
    else:
        services = ""
        # uploaded_file = st.file_uploader("Upload any form of ID to verify information",
        #                                  type=["jpeg", "jpg", "png", "pdf"], key="reg_user_id_doc")

    if st.button("Submit Registration"):
        if not reg_user_id or not reg_password:
            st.error("Please fill in both User ID and Password.")
        else:
            try:
                user_existing_df = conn.read(worksheet="Users", ttl=0)
            except Exception:
                user_existing_df = pd.DataFrame(columns=[
                    "user_id", "password", "role", "first_name", "last_name", "city", "state", "zip", "services"
                ])

            if reg_user_id in user_existing_df["user_id"].astype(str).values:
                st.error(f"User ID '{reg_user_id}' is already taken. Please choose another one.")
            else:
                user_new_row = pd.DataFrame([{
                    "user_id": reg_user_id,
                    "password": reg_password,
                    "role": role,
                    "first_name": first_name or role,
                    "last_name": last_name or "User",
                    "city": city,
                    "state": state,
                    "zip": utils.clean_zip_display(zip_code),
                    "services": services
                }])

                user_updated_df = pd.concat([user_existing_df, user_new_row], ignore_index=True)
                conn.update(worksheet="Users", data=user_updated_df)
                st.success(f"Registered successfully as {role}! You can now log in.")