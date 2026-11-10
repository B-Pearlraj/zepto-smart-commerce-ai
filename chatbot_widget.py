"""
Floating document-chatbot widget for the Streamlit app.

Streamlit renders components inside an iframe, so a "fixed" button
placed there would not float over the page. This helper runs a tiny
script inside that iframe which copies chatbot.css and chatbot.js into
the PARENT page, so the round avatar button floats at the bottom-right
of the whole app (same as on a normal website).

Usage in app.py (one line, after st.set_page_config):

    from chatbot_widget import render_document_chatbot
    render_document_chatbot(API_BASE_URL)

chatbot.css and chatbot.js are read from the same folder as this file.
If they are missing there, the widget falls back to loading them from
the API server (<API_BASE_URL>/chatbot/chatbot.js).
"""

import json
from pathlib import Path
from typing import List, Optional

import streamlit.components.v1 as components

_APP_DIR = Path(__file__).resolve().parent


def _read_asset(name: str) -> Optional[str]:
    path = _APP_DIR / name

    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _js_safe(value) -> str:
    """JSON for embedding inside a <script> block."""
    return json.dumps(value).replace("</", "<\\/")


def render_document_chatbot(
    api_base_url: str,
    *,
    title: str = "Document Assistant",
    subtitle: str = "Online - ask me about our documents",
    greeting: Optional[str] = None,
    suggestions: Optional[List[str]] = None,
    avatar_url: Optional[str] = None,
    theme: str = "light",
    offset_bottom: int = 96,
    offset_side: int = 24,
) -> None:
    """
    Add the floating chat widget to the current Streamlit page.

    offset_bottom defaults to 96 px so the button sits above
    Streamlit's chat input bar instead of covering its send button.
    """

    config = {
        "apiBase": api_base_url.rstrip("/"),
        "title": title,
        "subtitle": subtitle,
        "theme": theme,
        "offsetBottom": offset_bottom,
        "offsetSide": offset_side,
        "loadCss": False,   # this helper injects the CSS itself
    }

    if greeting:
        config["greeting"] = greeting

    if suggestions:
        config["suggestions"] = suggestions

    if avatar_url:
        config["avatarUrl"] = avatar_url

    css = _read_asset("chatbot.css")
    js = _read_asset("chatbot.js")

    remote_css = f"{config['apiBase']}/chatbot/chatbot.css"
    remote_js = f"{config['apiBase']}/chatbot/chatbot.js"

    html = f"""
    <script>
    (function () {{
      var host;

      try {{
        host = window.parent;
        void host.document.body;            // throws if the parent is cross-origin
      }} catch (e) {{
        return;
      }}

      var doc = host.document;

      // Already installed by an earlier Streamlit rerun: nothing to do.
      // Only the theme may have changed (dark / light toggle): apply it.
      if (host.__zeptoChatbotLoaded) {{
        var existing = doc.querySelector(".zbot-root");
        if (existing) {{
          existing.setAttribute("data-theme", {_js_safe(theme)});
        }}
        return;
      }}

      host.ZEPTO_CHATBOT_CONFIG = {_js_safe(config)};

      var localCss = {_js_safe(css)};
      var localJs = {_js_safe(js)};

      // ---- stylesheet
      if (!doc.getElementById("zbot-css")) {{
        if (localCss) {{
          var style = doc.createElement("style");
          style.id = "zbot-css";
          style.textContent = localCss;
          doc.head.appendChild(style);
        }} else {{
          var link = doc.createElement("link");
          link.id = "zbot-css";
          link.rel = "stylesheet";
          link.href = {_js_safe(remote_css)};
          doc.head.appendChild(link);
        }}
      }}

      // ---- script (runs in the parent page, so `document` is the app page)
      var script = doc.createElement("script");

      if (localJs) {{
        script.textContent = localJs;
      }} else {{
        script.src = {_js_safe(remote_js)};
      }}

      doc.body.appendChild(script);
    }})();
    </script>
    """

    components.html(html, height=0)
