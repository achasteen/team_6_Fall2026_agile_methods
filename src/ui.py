import html
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
.block-container {
    max-width: 1040px;
    padding-top: 2.5rem;
    padding-bottom: 6rem;
}
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


def go_to(view):
    """
    Switches the dashboard view. Applied by app.py before the nav control renders.
    """
    st.session_state.pending_view = view
    st.rerun()
