"""
Floating document chatbot for the Streamlit UI.

Streamlit cannot run JavaScript from st.markdown, so this helper uses a
zero-height st.components.v1.html frame. Its script copies chatbot.css and
chatbot.js into the MAIN page (window.parent), where the widget floats at
the bottom-right corner above the Streamlit app.

Files read from the same folder as this module:
    chatbot.css
    chatbot.js
    chatbot-avatar.png   (optional - falls back to Logo-PTS.png)
"""

import base64
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


BASE_DIR = Path(__file__).resolve().parent

AVATAR_CANDIDATES = ("chatbot-avatar.png", "Logo-PTS.png")


@st.cache_resource
def _load_assets() -> dict:
    """Read the widget files once per server process."""

    css_path = BASE_DIR / "chatbot.css"
    js_path = BASE_DIR / "chatbot.js"

    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""

    avatar_uri = ""

    for name in AVATAR_CANDIDATES:
        candidate = BASE_DIR / name

        if candidate.exists():
            encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
            avatar_uri = f"data:image/png;base64,{encoded}"
            break

    return {"css": css, "js": js, "avatar": avatar_uri}


def _js_string(value: str) -> str:
    """JSON-encode a string so it is safe inside an inline <script>."""

    return json.dumps(value).replace("</", "<\\/")


def inject_chatbot(
    api_base_url: str,
    theme: str = "dark",
    title: str = "Zepto Assistant",
    subtitle: str = "Ask me about our documents",
    bottom_offset: int = 88,
    right_offset: int = 24,
) -> None:
    """
    Add the floating chat widget to the page.

    Safe to call on every Streamlit rerun: the widget is created once and
    only its settings (e.g. light/dark theme) are updated afterwards, so an
    open conversation is never lost.

    bottom_offset keeps the round button above Streamlit's chat input box.
    """

    assets = _load_assets()

    if not assets["js"] or not assets["css"]:
        st.warning(
            "Chatbot files (chatbot.js / chatbot.css) were not found next "
            "to app.py, so the chat widget is disabled."
        )
        return

    config = {
        "apiBase": api_base_url.rstrip("/"),
        "theme": "light" if theme == "light" else "dark",
        "avatarUrl": assets["avatar"],
        "title": title,
        "subtitle": subtitle,
        "bottomOffset": bottom_offset,
        "rightOffset": right_offset,
    }

    config_js = json.dumps(config).replace("</", "<\\/")

    html = f"""
<script>
(function () {{
  try {{
    var p = window.parent;
    var d = p.document;

    if (!d.getElementById("zc-style")) {{
      var style = d.createElement("style");
      style.id = "zc-style";
      style.textContent = {_js_string(assets["css"])};
      d.head.appendChild(style);
    }}

    p.__ZC_CONFIG__ = {config_js};

    if (!d.getElementById("zc-script")) {{
      var script = d.createElement("script");
      script.id = "zc-script";
      script.textContent = {_js_string(assets["js"])};
      d.body.appendChild(script);
    }} else if (p.ZeptoChatbot) {{
      p.ZeptoChatbot.init(p.__ZC_CONFIG__);
    }}

    // Hide this empty helper frame so it takes no space on the page.
    var frame = window.frameElement;
    if (frame) {{
      var holder = frame.closest('[data-testid="stElementContainer"]') ||
                   frame.closest(".element-container") || frame;
      holder.style.display = "none";
    }}
  }} catch (err) {{
    console.warn("Chatbot widget could not start:", err);
  }}
}})();
</script>
"""

    components.html(html, height=0)
