# Samaritan Network App


## Link to App
Link to the deployed app: https://team6fall2026agilemethodsgit-qkixjx24bvbybsau9s9pey.streamlit.app

## Project Structure

```text
team_6_Fall2026_agile_methods/
├── app.py                          # Main Entry Point
├── requirements.txt                # Dependencies List
├── .gitignore                      # Prevent commit of secrets.toml
├── db/
│   └── schema.sql                  # Postgres tables (users, requests, notifications, messages)
├── src/
│   ├── db.py                       # All database reads and writes (Neon Postgres)
│   ├── utils.py                    # Helper Functions
│   ├── ui.py                       # Shared styling and UI helpers (CSS, tags, cards, navigation)
│   └── views/                      # Independent screen modules
│       ├── logged_in_samaritan.py  # Logged In Samaritan Views and Logic
│       ├── logged_in_user.py       # Logged In User Views and Logic
│       ├── logged_out_login.py     # Login View and Logic
│       ├── logged_out_register.py  # Register View and Logic
│       ├── messages.py             # Messages sidebar and conversation View and Logic
│       └── notifications.py        # Notification Inbox View and Logic
├── .streamlit/                     # config.toml (theme, committed) and secrets.toml (never committed)
```

`ui.py` holds the visual system: fonts and colors live in `.streamlit/config.toml`, extra CSS and small render helpers live in `ui.py`. Render user-entered text through `ui.esc()` when it goes inside HTML. To switch dashboard views from a view, call `ui.go_to("<view_id>")`.

`app.py` is reserved for `session_state` management and overall flow for when views are presented. It is NOT a place to render views and logic

`utils.py` is for helper functions that may be used across views

`db.py` is the only place that talks to the database. Views call its functions (`db.get_user`, `db.accept_request`, ...) rather than writing SQL themselves

The remaining files are reserved for specific views and logic. Hopefully this will make the code easier to maintain, extend and concurrently modify

## Messaging

Once a Samaritan accepts a request, the requester and the Samaritan get a private conversation about it. Only those two people can open it.

- **Starting one:** use "Message ..." on an accepted request card. The conversation appears in the sidebar once the first message is sent.
- **Sidebar inbox:** the left sidebar lists every conversation, newest first, with the other person, the request, the latest message and an unread count. On phones the sidebar is a drawer, opened with the "Messages" button in the top bar.
- **Conversation:** clicking a conversation (or "Message ..." on a request card) opens it in the main area. Opening it marks its messages as read.
- **Refresh:** the inbox and an open conversation check for new messages every 15 seconds.

Messages are stored in the `messages` table; `read_at` is set when the recipient opens the conversation.

## Database

The app uses a [Neon](https://neon.tech) Postgres database (project `lively-mouse-89614258`, branch `production`). It replaced the Google Sheet; the sheet is no longer read or written by the app. Browse or edit the data in the Neon console under **Tables**.

- Tables are defined in `db/schema.sql`, and the app applies that file automatically the first time it connects. A brand-new database sets itself up. To change the schema, edit that file and keep every statement re-runnable (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- Accepting a request is a single `UPDATE ... WHERE status = 'pending'`, so two Samaritans can't accept the same request.
- To try changes without touching real data, create a Neon branch (an instant copy of the database) and point your local `secrets.toml` at it.

## Repository Management

For new features, please create a branch, develop the feature and submit a pull request so we can all review it before merging it into main

## Secrets Management

To enable the database features for local development, a secrets.toml file will need to be created in the `.streamlit` folder on your local:

```toml
[connections.neon]
url = "postgresql+psycopg://<user>:<password>@<host>/neondb?sslmode=require"
```

The necessary contents will be sent over chat. Use the "direct" (non-pooled) connection string from the Neon console and change the `postgresql://` prefix to `postgresql+psycopg://`.

## Deployment (Streamlit Community Cloud)

1. In the app's settings on share.streamlit.io, open **Secrets** and add the same `[connections.neon]` block as your local `secrets.toml`. The old `[connections.gsheets]` block is no longer used and can be removed.
2. Deploy the branch. Streamlit Cloud installs `requirements.txt`, and the app creates or upgrades the database tables on first use.

Please do NOT commit this `secrets.toml` file or share.

## Github Copilot Code Review

Github Copilot code review is enabled for pull requests. It will automatically run a code review when you submit a pull request.

Another reason to follow the practice of creating a branch and then submitting a pull request to merge.


