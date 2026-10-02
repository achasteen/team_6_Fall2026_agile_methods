import html
import time

import streamlit as st

# Muted pastel tones for status tags (background, text)
TAG_TONES = {
    "yellow": ("#FBF3DB", "#956400"),
    "green": ("#EDF3EC", "#346538"),
    "blue": ("#E1F3FE", "#1F6C9F"),
    "red": ("#FDEBEC", "#9F2F2D"),
    "gray": ("#F1F1EF", "#787774"),
}

STYLES = """
<style>
.block-container, [data-testid="stBottomBlockContainer"] {
    max-width: 1040px;
    padding-top: 2.5rem;
    padding-bottom: 6rem;
}
[data-testid="stBottomBlockContainer"] { padding-top: 1rem; padding-bottom: 2rem; }
header[data-testid="stHeader"] { background: transparent; }

/* Faint warm light behind the page so it never reads as flat */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background: radial-gradient(56rem 36rem at 90% -10%, rgba(214, 196, 160, 0.14), transparent 60%);
}

h1 { letter-spacing: -0.03em; line-height: 1.1 !important; text-wrap: balance; color: #111111; }
h2, h3 { letter-spacing: -0.02em; text-wrap: balance; color: #111111; }
.lede, .meta, .card-body { text-wrap: pretty; line-height: 1.6; }

.wordmark {
    font-weight: 600;
    letter-spacing: -0.01em;
    color: #111111;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}
.wordmark-mark {
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 6px;
    background: #111111;
    color: #FBFBFA;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
}

.lede { font-size: 1.125rem; color: #5F6368; max-width: 34rem; }
.meta { color: #787774; font-size: 0.875rem; }
.mono { font-family: "Geist Mono", ui-monospace, monospace; font-size: 0.85em; }
.card-title { font-weight: 600; font-size: 1.05rem; color: #111111; margin: 0; }
.card-body { color: #2F3437; max-width: 65ch; }

.tag {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    white-space: nowrap;
}

.step { padding: 1rem 0; border-bottom: 1px solid #EAEAEA; }
.step:last-child { border-bottom: none; }
.step-title { font-weight: 600; color: #111111; margin-bottom: 0.15rem; }

/* Cards: hairline border, ultra-soft lift on hover, gentle entrance */
[class*="st-key-card-"] {
    background: #FFFFFF;
    transition: box-shadow 200ms cubic-bezier(0.16, 1, 0.3, 1), transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
    animation: rise 600ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
[class*="st-key-card-"]:hover { box-shadow: 0 2px 8px rgba(17, 17, 17, 0.04); }
[class*="st-key-card-"] .meta { margin-bottom: 0.35rem !important; }

/* Phones: keep the log-in form near the top of the screen */
@media (max-width: 640px) {
    .block-container { padding-top: 1.5rem; }
    .steps { display: none; }
}
[class*="st-key-panel-"] { background: #FFFFFF; }

/* Sidebar conversation list */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.25rem; }
.dm-heading { font-weight: 600; font-size: 1rem; color: #111111; margin: 0 0 0.5rem; }
[class*="st-key-dmrow-"] { position: relative; }
[class*="st-key-dmrow-"] > [data-testid="stElementContainer"]:has([data-testid="stButton"]) {
    position: absolute;
    inset: 0;
    margin: 0;
}
[class*="st-key-dmrow-"] [data-testid="stButton"],
[class*="st-key-dmrow-"] [data-testid="stButton"] button {
    width: 100%;
    height: 100%;
}
[class*="st-key-dmrow-"] [data-testid="stButton"] button { opacity: 0; cursor: pointer; }
.dm-row {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    padding: 0.65rem 0.6rem;
    border-radius: 8px;
    transition: background-color 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
[class*="st-key-dmrow-"]:hover .dm-row { background: rgba(17, 17, 17, 0.04); }
[class*="st-key-dmrow-"]:has(button:focus-visible) .dm-row { outline: 2px solid #111111; outline-offset: -2px; }

/* "Messages" shortcut in the top bar opens the sidebar drawer; only needed on phones */
.st-key-btn_mobile_messages { display: none; }
@media (max-width: 768px) { .st-key-btn_mobile_messages { display: block; } }
.dm-row.dm-open { background: #FFFFFF; box-shadow: inset 0 0 0 1px #EAEAEA; }
.dm-avatar {
    flex: none;
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 10px;
    background: #E6E5E1;
    color: #2F3437;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
}
.dm-main { flex: 1; min-width: 0; }
.dm-top { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }
.dm-name, .dm-request, .dm-preview { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dm-name { font-weight: 600; font-size: 0.92rem; color: #111111; }
.dm-time { flex: none; font-size: 0.75rem; color: #787774; }
.dm-request { font-size: 0.78rem; color: #787774; }
.dm-preview { font-size: 0.85rem; color: #5F6368; }
.dm-has-unread .dm-preview { color: #111111; font-weight: 500; }
.dm-unread {
    flex: none;
    align-self: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.35rem;
    border-radius: 9999px;
    background: #111111;
    color: #FBFBFA;
    font-size: 0.7rem;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

/* Message thread */
.msg { display: flex; flex-direction: column; margin: 0 0 0.9rem; }
.msg-mine { align-items: flex-end; }
.msg-theirs { align-items: flex-start; }
.msg-bubble {
    max-width: min(32rem, 85%);
    padding: 0.6rem 0.9rem;
    border-radius: 12px;
    line-height: 1.5;
    overflow-wrap: anywhere;
}
.msg-mine .msg-bubble { background: #111111; color: #FBFBFA; border-bottom-right-radius: 4px; }
.msg-theirs .msg-bubble { background: #FFFFFF; color: #2F3437; border: 1px solid #EAEAEA; border-bottom-left-radius: 4px; }
.msg-meta { color: #787774; font-size: 0.75rem; margin-top: 0.25rem; }

.stButton button, .stFormSubmitButton button {
    transition: transform 160ms cubic-bezier(0.16, 1, 0.3, 1), background-color 200ms ease;
}
.stButton button:active, .stFormSubmitButton button:active { transform: scale(0.98); }

@keyframes rise {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""


def inject_styles():
    st.markdown(STYLES, unsafe_allow_html=True)


def esc(text):
    """
    Escapes user-provided text for use inside the HTML snippets below
    (no HTML injection, no LaTeX via $, newlines kept as line breaks).
    """
    if text is None:
        return ""
    escaped = html.escape(str(text)).replace("$", "&#36;")
    return escaped.replace("\r\n", "\n").replace("\n", "<br>")


def html_block(markup):
    st.markdown(markup, unsafe_allow_html=True)


def tag(label, tone="gray"):
    bg, fg = TAG_TONES.get(tone, TAG_TONES["gray"])
    return f'<span class="tag" style="background:{bg};color:{fg}">{html.escape(label)}</span>'


def wordmark():
    st.markdown(
        '<div class="wordmark"><span class="wordmark-mark">S</span>Samaritan Services</div>',
        unsafe_allow_html=True,
    )


def lede(text):
    html_block(f'<p class="lede">{esc(text)}</p>')


def meta(text):
    html_block(f'<p class="meta">{esc(text)}</p>')


def request_details(title, description, meta_text, tags_html=""):
    """
    Renders the text portion of a request card: title with status tags, description, and a meta line.
    """
    html_block(
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap">'
        f'<p class="card-title">{esc(title)}</p><div style="display:flex;gap:0.4rem">{tags_html}</div></div>'
        f'<p class="card-body" style="margin:0.4rem 0 0.5rem">{esc(description)}</p>'
        f'<p class="meta" style="margin:0">{meta_text}</p>'
    )


def empty_state(title, body):
    html_block(
        '<div style="padding:2.5rem 0 1rem">'
        f'<p class="card-title" style="margin-bottom:0.25rem">{esc(title)}</p>'
        f'<p class="meta" style="max-width:34rem">{esc(body)}</p></div>'
    )


def flash(message, icon=":material/check_circle:"):
    """
    Queues a toast to show after the next rerun.
    """
    st.session_state.flash = (message, icon)


def show_flash():
    if "flash" in st.session_state:
        message, icon = st.session_state.pop("flash")
        st.toast(message, icon=icon)


def open_thread(request_id):
    """
    Opens the message thread for a request. Applied by app.py on the next run.
    """
    st.session_state.pending_thread = str(request_id)
    st.session_state.sidebar_action = "close"  # so the chat isn't hidden behind the drawer on phones
    st.rerun()


def open_sidebar():
    st.session_state.sidebar_action = "open"


_SIDEBAR_SCRIPT = """
<script>
(() => {
  if (window.innerWidth > 768) return;  // phones only; on desktop the sidebar is always shown
  // Streamlit can run this script more than once; act only once per request
  const runId = %s;
  window.__sidebarActions = window.__sidebarActions || {};
  if (window.__sidebarActions[runId]) return;
  window.__sidebarActions[runId] = true;

  const wantOpen = %s;
  const selector = wantOpen
    ? '[data-testid="stExpandSidebarButton"]'
    : '[data-testid="stSidebarCollapseButton"] button';
  const tryClick = (attempts) => {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (sidebar && (sidebar.getAttribute("aria-expanded") === "true") === wantOpen) return;
    const el = document.querySelector(selector);
    if (el) el.click();
    else if (attempts > 0) setTimeout(() => tryClick(attempts - 1), 100);
  };
  tryClick(20);
})();
</script>
"""


def apply_sidebar_action():
    """
    Opens or closes the sidebar drawer on phones when a view asked for it this run.
    Streamlit has no API for this, so it clicks the sidebar's own toggle button.
    """
    action = st.session_state.pop("sidebar_action", None)
    if action not in ("open", "close"):
        return
    # A fresh run id makes this a new element, so the script runs for this request
    run_id = repr(f"{action}-{time.time()}")
    st.html(_SIDEBAR_SCRIPT % (run_id, "true" if action == "open" else "false"), unsafe_allow_javascript=True)


def close_thread():
    st.session_state.pop("open_thread", None)


def go_to(view):
    """
    Switches the dashboard view. Applied by app.py before the nav control renders.
    """
    st.session_state.pending_view = view
    st.rerun()
