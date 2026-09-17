# Samaritan Network App


## Link to App
Link to the deployed app: https://team6fall2026agilemethodsgit-qkixjx24bvbybsau9s9pey.streamlit.app

## Project Structure

```text
team_6_Fall2026_agile_methods/
├── app.py                          # Main Entry Point
├── requirements.txt                # Dependencies List
├── .gitignore                      # Prevent commit of secrets.toml
├── src/
│   ├── utils.py                    # Helper Functions
│   └── views/                      # Independent screen modules
│       ├── logged_in_samaritan.py  # Logged In Samaritan Views and Logic
│       ├── logged_in_user.py       # Logged In User Views and Logic
│       └── logged_out_login.py     # Login View and Logic
│       └── logged_out_register.py  # Register View and Logic
├── .streamlit/                     # Folder for secrets.toml
```

`app.py` is reserved for `session_state` management and overall flow for when views are presented. It is NOT a place to render views and logic

`utils.py` is for helper functions that may be used across views

The remaining files are reserved for specific views and logic. Hopefully this will make the code easier to maintain, extend and concurrently modify

## Repository Management

For new features, please create a branch, develop the feature and submit a pull request so we can all review it before merging it into main

## Secrets Management

To enable the database features for local development, a secrets.toml file will need to be created in the `.streamlit` folder on your local

The necessary contents will be sent over chat.

Please do NOT commit this `secrets.toml` file or share.


