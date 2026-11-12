import os
import re
import time

import requests
import streamlit as st

from api_client import APIClient


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Zepto Smart Commerce AI",
    page_icon="Logo-PTS.png",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    "https://zepto-smart-commerce-ai.onrender.com",
)


@st.cache_resource
def get_api(base_url: str) -> APIClient:
    """One shared API client (and HTTP session) for all reruns."""
    return APIClient(base_url)


api = get_api(API_BASE_URL)


# ------------------------------------------------------------
# Sidebar status check
#
# The sidebar status comes from a quick check of the backend's
# /health endpoint. To avoid 429 errors the result is remembered,
# but a GOOD result is remembered for 60 seconds while a BAD one is
# only remembered for 5 seconds, so a failed check made while the
# backend was still waking up does not stay red after it is ready.
# ------------------------------------------------------------

STATUS_TTL_ONLINE_SECONDS = 60
STATUS_TTL_PROBLEM_SECONDS = 5


def get_service_status(force: bool = False) -> dict:
    cached = st.session_state.get("service_status")

    if cached and not force:
        age = time.time() - cached["checked_at"]
        ttl = (
            STATUS_TTL_ONLINE_SECONDS
            if cached["state"] == "online"
            else STATUS_TTL_PROBLEM_SECONDS
        )

        if age < ttl:
            return cached

    status = api.ping()
    status["checked_at"] = time.time()
    st.session_state.service_status = status

    return status


def mark_service_online():
    """A successful order lookup / prediction proves the backend is up."""
    st.session_state.service_status = {
        "state": "online",
        "detail": "",
        "checked_at": time.time(),
    }


# ============================================================
# FIELD DEFAULTS  (the full ML feature set. When an order is
# looked up, its stored values overwrite these defaults; any
# field an order doesn't have falls back to the value below.)
# ============================================================

DEFAULT_PAYLOAD = {
    "city": "Chennai",
    "city_tier": 1,
    "customer_lat": 13.0827,
    "customer_lon": 80.2707,
    "store_id": "DS001",
    "store_lat": 13.0800,
    "store_lon": 80.2700,
    "delivery_zone": "urban",
    "distance_km": 1.8,
    "distance_band": "0-2",
    "distance_to_radius_ratio": 0.18,
    "service_radius_km": 10.0,
    "within_service_radius": 1,
    "item_count": 5,
    "order_amount": 450.0,
    "order_amount_band": "medium",
    "order_weight_kg": 2.0,
    "order_amount_per_kg": 225.0,
    "order_year": 2026,
    "order_month": 9,
    "order_day": 10,
    "order_hour": 18,
    "order_dayofweek": 3,
    "is_month_start": 0,
    "is_month_end": 0,
    "is_peak_hour": 0,
    "is_weekend": 0,
    "time_of_day": "evening",
    "weather_condition": "clear",
    "weather_severity": 0,
    "rainfall_mm": 0.0,
    "has_rain": 0,
    "traffic_index": 30.0,
    "traffic_level": "low",
    "road_type": "main_road",
    "current_rider_load": 2.0,
    "previous_acceptance_rate": 0.85,
    "rider_earnings_today": 850.0,
    "rider_experience_months": 24.0,
    "rider_experience_band": "experienced",
    "rider_rating": 4.7,
    "rider_rating_band": "high",
    "vehicle_type": "bike",
    "current_incentive": 20.0,
    "membership_type": "pass_plus",
    "historical_delivery_cost": 48.0,
    "historical_travel_time": 18.0,
    "demand_level": "medium",
    "festival_day_flag": 0,
}


# ============================================================
# CUSTOM CSS  —  Zepto-pattern theme
# (signature Zepto violet/purple + white, bold rounded UI,
#  green for positive states, peach/yellow for highlights —
#  matching Zepto's own light, high-energy quick-commerce look)
# ============================================================

ZEPTO_PURPLE = "#8B2FF8"
ZEPTO_PURPLE_DARK = "#6E1FD1"

# ------------------------------------------------------------
# THEMES — the app opens in DARK mode. The ◐ button in the
# top-right switches between dark and light.
# ------------------------------------------------------------

if "theme" not in st.session_state:
    st.session_state.theme = "dark"          # default on first open


def toggle_theme():
    st.session_state.theme = (
        "light" if st.session_state.theme == "dark" else "dark"
    )


THEMES = {
    "dark": {
        "scheme": "dark",
        "bg": "#0F0B14",
        "sidebar": "#150F1C",
        "surface": "#1B1424",
        "surface_alt": "#231A2E",
        "border": "#32254A",
        "ink": "#F4EFFA",
        "muted": "#A99DB8",
        "faint": "#8A7E99",
        "accent_text": "#C9A2FF",
        "code_bg": "#2B1F3D",
        "shadow": "rgba(0, 0, 0, 0.35)",
        "green": "#34D17F",
        "warn_text": "#FFC266",
        "pill_ok_bg": "rgba(52, 209, 127, 0.15)",
        "pill_warn_bg": "rgba(255, 183, 77, 0.16)",
        "a_success": "rgba(52, 209, 127, 0.14)",
        "a_warning": "rgba(255, 183, 77, 0.14)",
        "a_error": "rgba(255, 90, 90, 0.14)",
        "a_info": "rgba(139, 47, 248, 0.18)",
        # opaque versions (so Streamlit's own light layer can't show through)
        "s_success": "#12301F",
        "s_warning": "#3A2E14",
        "s_error": "#3E1A24",
        "s_info": "#2A1A45",
        "t_success": "#7DF0B0",
        "t_warning": "#FFD58A",
        "t_error": "#FFB3B3",
        "t_info": "#E0CCFF",
    },
    "light": {
        "scheme": "light",
        "bg": "#FAF8FD",
        "sidebar": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_alt": "#FBF7FF",
        "border": "#EFE6FC",
        "ink": "#161119",
        "muted": "#7A6E88",
        "faint": "#A79BB3",
        "accent_text": ZEPTO_PURPLE_DARK,
        "code_bg": "#F1E6FE",
        "shadow": "rgba(139, 47, 248, 0.08)",
        "green": "#0CA750",
        "warn_text": "#B9720A",
        "pill_ok_bg": "rgba(12, 167, 80, 0.12)",
        "pill_warn_bg": "rgba(255, 183, 77, 0.18)",
        "a_success": "rgba(12, 167, 80, 0.10)",
        "a_warning": "rgba(255, 183, 77, 0.18)",
        "a_error": "rgba(229, 57, 53, 0.10)",
        "a_info": "rgba(139, 47, 248, 0.08)",
        "s_success": "#E6F6ED",
        "s_warning": "#FFF3DC",
        "s_error": "#FDE8E8",
        "s_info": "#F1E6FE",
        "t_success": "#0A5C2E",
        "t_warning": "#7A4A05",
        "t_error": "#8F1D1D",
        "t_info": "#4A1B8F",
    },
}

T = THEMES[st.session_state.theme]

THEME_VARS = f"""
:root {{
    color-scheme: {T["scheme"]};
    --bg: {T["bg"]};
    --sidebar: {T["sidebar"]};
    --surface: {T["surface"]};
    --surface-alt: {T["surface_alt"]};
    --border: {T["border"]};
    --ink: {T["ink"]};
    --muted: {T["muted"]};
    --faint: {T["faint"]};
    --accent-text: {T["accent_text"]};
    --code-bg: {T["code_bg"]};
    --shadow: {T["shadow"]};
    --green: {T["green"]};
    --warn-text: {T["warn_text"]};
    --pill-ok-bg: {T["pill_ok_bg"]};
    --pill-warn-bg: {T["pill_warn_bg"]};
    --a-success: {T["a_success"]};
    --a-warning: {T["a_warning"]};
    --a-error: {T["a_error"]};
    --a-info: {T["a_info"]};
    --s-success: {T["s_success"]};
    --s-warning: {T["s_warning"]};
    --s-error: {T["s_error"]};
    --s-info: {T["s_info"]};
    --t-success: {T["t_success"]};
    --t-warning: {T["t_warning"]};
    --t-error: {T["t_error"]};
    --t-info: {T["t_info"]};
    --purple: {ZEPTO_PURPLE};
    --purple-dark: {ZEPTO_PURPLE_DARK};
}}
"""

STATIC_CSS = """
/* Keep the header so the sidebar-collapse arrow (top-left) stays usable.
   Only hide the "Made with Streamlit" footer and the Deploy button. */
footer {visibility: hidden;}
div[data-testid="stToolbarActions"] {display: none;}
header[data-testid="stHeader"] {background: transparent;}
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] svg,
button[data-testid="stExpandSidebarButton"],
button[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] button {
    color: var(--ink) !important;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: var(--bg);
    color: var(--ink);
    font-family: "Poppins", "Segoe UI", sans-serif;
}

/* Bottom bar that wraps the chat input */
div[data-testid="stBottom"],
div[data-testid="stBottom"] > div,
div[data-testid="stBottomBlockContainer"] {
    background: var(--bg);
}
div[data-testid="stBottomBlockContainer"] {padding-top: 8px;}

/* ---------- Text colours (both themes) ---------- */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] strong,
.stApp label,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    color: var(--ink);
}
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    color: var(--muted) !important;
}
[data-testid="stMarkdownContainer"] code {
    background: var(--code-bg);
    color: var(--accent-text);
    border-radius: 6px;
    padding: 1px 6px;
}

h1, h2, h3, .brand-title, .welcome-title {
    font-family: "Poppins", "Segoe UI", sans-serif;
    letter-spacing: -0.01em;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background: var(--sidebar);
}
section[data-testid="stSidebar"] {border-right: 1px solid var(--border);}

section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    background: var(--purple);
    color: #FFFFFF;
    border: none;
    border-radius: 999px;
    font-weight: 700;
    text-align: center;
    padding: 10px 16px;
    box-shadow: 0 4px 14px rgba(139, 47, 248, 0.28);
}
section[data-testid="stSidebar"] .stButton > button p {color: #FFFFFF;}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--purple-dark);
    color: #FFFFFF;
}

/* ---------- Expanders ---------- */
div[data-testid="stExpander"] {
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
}
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] summary {
    background: transparent;
    color: var(--ink);
}
div[data-testid="stExpander"] summary svg {color: var(--ink);}
div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary span {color: var(--ink) !important;}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] * {color: var(--ink);}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] code {color: var(--accent-text);}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {color: var(--ink);}
/* Make "Created by ..." and other plain text always visible */
[data-testid="stMarkdownContainer"] a {color: var(--accent-text);}

/* ---------- Alerts (success / warning / error / info) ----------
   Opaque backgrounds + matching text colour so they are readable in
   BOTH dark and light mode (Streamlit's own light layer was showing
   through the translucent colours and hiding the light text). */
div[data-testid="stAlert"],
div[data-testid="stAlert"] > div,
div[data-testid="stAlert"] [data-baseweb="notification"] {
    background: var(--s-info) !important;
    background-color: var(--s-info) !important;
    --alert-text: var(--t-info);
    border-radius: 12px;
    border: none !important;
}
div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) > div,
div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) [data-baseweb="notification"] {
    background: var(--s-success) !important; background-color: var(--s-success) !important; --alert-text: var(--t-success);
}
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) > div,
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-baseweb="notification"] {
    background: var(--s-warning) !important; background-color: var(--s-warning) !important; --alert-text: var(--t-warning);
}
div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) > div,
div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) [data-baseweb="notification"] {
    background: var(--s-error) !important; background-color: var(--s-error) !important; --alert-text: var(--t-error);
}
div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]),
div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) > div,
div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) [data-baseweb="notification"] {
    background: var(--s-info) !important; background-color: var(--s-info) !important; --alert-text: var(--t-info);
}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] li,
div[data-testid="stAlert"] strong,
div[data-testid="stAlert"] code,
div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
    color: var(--alert-text, var(--ink)) !important;
}

/* ---------- Branding / welcome ---------- */
.brand-row {display: flex; align-items: center; gap: 12px; margin-bottom: 4px;}

.brand-circle {
    width: 36px; height: 36px; border-radius: 11px;
    background: var(--purple);
    box-shadow: 0 4px 14px rgba(139, 47, 248, 0.35);
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
}
.brand-circle.lg {
    width: 84px; height: 84px; border-radius: 24px;
    margin: 0 auto 18px auto; font-size: 40px;
}

.brand-title {font-size: 19px; font-weight: 800; color: var(--ink); margin: 0;}
.brand-sub {font-size: 12.5px; color: var(--muted); margin: 0;}

.welcome-wrap {text-align: center; margin-top: 7vh;}
.welcome-title {font-size: 28px; font-weight: 800; color: var(--ink); margin-bottom: 6px;}
.welcome-sub {font-size: 15px; color: var(--muted); max-width: 580px; margin: 0 auto;}
.welcome-sub code {
    background: var(--code-bg);
    color: var(--accent-text);
    padding: 1px 6px;
    border-radius: 6px;
}

.example-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 12.5px;
    color: var(--muted);
    max-height: 220px;
    overflow-y: auto;
    text-align: left;
    margin-top: 22px;
    box-shadow: 0 2px 10px var(--shadow);
}

/* ---------- Chat ---------- */
div[data-testid="stChatMessage"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 6px 8px;
    box-shadow: 0 2px 10px var(--shadow);
}

.result-card {
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px;
    text-align: center;
}
.result-label {color: var(--muted); font-size: 12.5px; font-weight: 600; margin-bottom: 4px;}
.result-value {color: var(--accent-text); font-size: 22px; font-weight: 800;}

.pill {display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12.5px; font-weight: 700;}
.pill-ok {background: var(--pill-ok-bg); color: var(--green);}
.pill-warn {background: var(--pill-warn-bg); color: var(--warn-text);}

.diff-row {font-size: 12.5px; color: var(--muted); font-family: "SFMono-Regular", Consolas, monospace; margin-bottom: 2px;}
.diff-key {color: var(--accent-text); font-weight: 650;}
.diff-old {color: var(--faint); text-decoration: line-through;}
.diff-new {color: var(--green); font-weight: 700;}

div[data-testid="stChatInput"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    box-shadow: 0 2px 10px var(--shadow);
    max-width: 900px;
    margin: 0 auto;
}
div[data-testid="stChatInput"] > div,
div[data-testid="stChatInput"] textarea {
    background: var(--surface) !important;
    color: var(--ink) !important;
}
div[data-testid="stChatInput"] textarea::placeholder {
    color: var(--faint) !important;
    opacity: 1 !important;
}

.stButton > button[kind="primary"],
button[data-testid="stChatInputSubmitButton"] {
    background: var(--purple) !important;
    border-color: var(--purple) !important;
}
button[data-testid="stChatInputSubmitButton"] svg {fill: #FFFFFF !important;}

/* ---------- ◐ Theme toggle button (top-right) ---------- */
.st-key-theme_toggle {display: flex; justify-content: flex-end;}
.st-key-theme_toggle button {
    width: 44px; height: 44px; min-height: 44px;
    padding: 0;
    border-radius: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: 0 2px 10px var(--shadow);
}
.st-key-theme_toggle button p {font-size: 20px; line-height: 1; color: var(--ink);}
.st-key-theme_toggle button:hover {border-color: var(--purple);}
"""

css = "<style>" + THEME_VARS + STATIC_CSS + "</style>"

st.markdown(css, unsafe_allow_html=True)


# ============================================================
# PARSING / FORMATTING HELPERS
# ============================================================

def coerce_value(raw: str):
    raw = raw.strip()
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        return raw


def parse_feature_edits(text: str) -> dict:
    """
    Parses short chat-style field edits such as:
        distance_km: 5, order_amount: 900
        rider_rating = 3.2
    Only known feature keys are extracted; free-text is ignored.
    Used to let a user tweak a looked-up order before confirming.
    """

    parsed = {}

    fragments = []
    for line in text.strip().splitlines():
        fragments.extend(line.split(","))

    for fragment in fragments:
        fragment = fragment.strip()
        if not fragment:
            continue

        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.+)$", fragment)
        if not match:
            continue

        key, value = match.group(1).strip(), match.group(2).strip()
        if key in DEFAULT_PAYLOAD:
            parsed[key] = coerce_value(value)

    return parsed


def format_optional(value):
    return "N/A" if value is None else str(value)


def display_text(value, default: str = "N/A") -> str:
    """Show a value, or N/A when the database value is empty/NULL."""
    return default if value in (None, "") else str(value)


def to_float(value, default: float = 0.0) -> float:
    """Safe float conversion for numbers that may be NULL/None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# WORDS THAT MOVE THE CONVERSATION STATE MACHINE
# ============================================================

CONFIRM_WORDS = {"confirm", "yes", "y", "ok", "okay", "go", "predict", "confirmed"}
CANCEL_WORDS = {"cancel", "no", "n", "stop", "reset"}


# ============================================================
# ORDER LOOKUP
# ============================================================

def lookup_order(order_id_text: str) -> dict:
    """
    Step 1 of the flow: the user has typed an order ID.
    Look it up via the API and, if found, stage it in session
    state awaiting confirmation.
    """

    order_id = order_id_text.strip()

    if not order_id:
        return {"type": "error", "message": "Please enter an order ID."}

    try:
        order = api.get_order(order_id)

    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None

        if code == 429:
            message = (
                "The server is busy (rate limit). "
                "Please wait a few seconds and try again."
            )
        elif code == 503:
            message = (
                "The order database is waking up. "
                "Please try again in a few seconds."
            )
        elif code and code >= 500:
            message = (
                f"The order service hit an internal error (HTTP {code}). "
                "Please try again shortly."
            )
        else:
            message = f"Order lookup failed: {exc}"

        return {"type": "error", "message": message}

    except (requests.ConnectionError, requests.Timeout):
        return {
            "type": "error",
            "message": (
                "The backend is not responding yet. It may be starting up "
                "after being idle — wait about a minute and try again."
            ),
        }

    except Exception as exc:
        return {
            "type": "error",
            "message": f"Couldn't reach the order lookup service: {exc}",
        }

    mark_service_online()

    if order is None:
        return {"type": "order_not_found", "order_id": order_id}

    # Build the ML feature payload from the order row, falling back
    # to the platform defaults for anything the order didn't set.
    payload = dict(DEFAULT_PAYLOAD)
    for key in DEFAULT_PAYLOAD:
        if key in order and order[key] is not None:
            payload[key] = order[key]

    order_record = {"info": order, "payload": payload}

    st.session_state.pending_order = order_record
    st.session_state.flow_state = "awaiting_confirmation"

    return {"type": "order_found", "order": order_record, "changed": {}}


# ============================================================
# PREDICTION FLOW
# ============================================================

def run_prediction_for_pending_order() -> dict:
    """
    Step 2 of the flow: the user confirmed. Run the prediction
    for whatever order is currently staged in session state.
    """

    order_record = st.session_state.pending_order

    if not order_record:
        st.session_state.flow_state = "awaiting_order_id"
        return {
            "type": "error",
            "message": (
                "There's no order waiting for confirmation yet. "
                "Enter an order ID first, e.g. `ORD1001`."
            ),
        }

    payload = order_record["payload"]

    try:
        result = api.predict(payload)
    except Exception as exc:
        return {"type": "error", "message": f"Prediction failed: {exc}"}

    mark_service_online()

    st.session_state.flow_state = "awaiting_order_id"
    st.session_state.pending_order = None

    return {
        "type": "prediction",
        "order_info": order_record["info"],
        "payload": payload,
        "result": result,
    }


def handle_user_message(text: str) -> dict:
    """
    The chatbot's tiny state machine:

      awaiting_order_id       -> any text is treated as an order ID
      awaiting_confirmation   -> "confirm"/"yes" runs the prediction
                                  "cancel"/"no" drops the staged order
                                  "key: value" tweaks the staged order
                                  anything else is treated as a NEW order ID
    """

    stripped = text.strip()
    lowered = stripped.lower()

    if st.session_state.flow_state == "awaiting_confirmation":

        if lowered in CONFIRM_WORDS:
            return run_prediction_for_pending_order()

        if lowered in CANCEL_WORDS:
            st.session_state.flow_state = "awaiting_order_id"
            st.session_state.pending_order = None
            return {"type": "cancelled"}

        edits = parse_feature_edits(stripped)

        if edits:
            order_record = st.session_state.pending_order
            payload = order_record["payload"]

            changed = {
                key: (payload.get(key), value)
                for key, value in edits.items()
                if payload.get(key) != value
            }

            payload.update(edits)
            order_record["payload"] = payload
            st.session_state.pending_order = order_record

            return {"type": "order_found", "order": order_record, "changed": changed}

        # Doesn't look like confirm/cancel/an edit -> treat as a new order ID
        return lookup_order(stripped)

    # awaiting_order_id
    return lookup_order(stripped)


# ============================================================
# RENDERING
# ============================================================

def render_order_found(content: dict):

    order_record = content["order"]
    info = order_record["info"]
    changed = content.get("changed", {})

    if changed:
        st.markdown("**Updated fields for this order:**")
        for key, (old, new) in changed.items():
            st.markdown(
                f'<div class="diff-row"><span class="diff-key">{key}</span>: '
                f'<span class="diff-old">{old}</span> → '
                f'<span class="diff-new">{new}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("Type **confirm** to run the prediction with these updates.")
        return

    st.markdown(
        f"Found order **`{info.get('order_id')}`** — "
        f"{display_text(info.get('customer_name'))}"
    )
    st.markdown(
        f"🛒 {display_text(info.get('product_name'))}  •  "
        f"Status: `{display_text(info.get('order_status'))}`"
    )

    st.markdown("")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">📍 City</div>'
            f'<div class="result-value" style="font-size:18px;">{display_text(info.get("city"))}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">📏 Distance</div>'
            f'<div class="result-value" style="font-size:18px;">{to_float(info.get("distance_km")):.1f} km</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">💵 Order Amount</div>'
            f'<div class="result-value" style="font-size:18px;">₹{to_float(info.get("order_amount")):.0f}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    st.markdown(
        "Type **confirm** (or **yes**) to run the delivery prediction for this "
        "order, **cancel** to drop it, or enter a different order ID to look "
        "up another one. You can also tweak a field first — e.g. `distance_km: 5`."
    )


def render_order_not_found(content: dict):
    st.warning(
        f"No order found with ID `{content['order_id']}`. "
        "Double-check the ID, or try one of the sample orders "
        "**ORD1001 – ORD1010**."
    )


def render_cancelled():
    st.info("Order cancelled. Enter a new order ID whenever you're ready.")


def render_prediction_message(content: dict):

    payload = content["payload"]
    result = content["result"]
    info = content.get("order_info", {})

    st.markdown(
        f"✅ Confirmed — here's the prediction for order "
        f"**`{info.get('order_id', 'N/A')}`** "
        f"({display_text(info.get('customer_name'))}, "
        f"{display_text(info.get('product_name'))})."
    )

    st.markdown("")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">💰 Delivery Charge</div>'
            f'<div class="result-value">₹{result["delivery_charge"]:.2f}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">⏱️ Estimated Delivery Time</div>'
            f'<div class="result-value">{result["delivery_time_minutes"]:.1f} min</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c3:
        probability = float(result["rider_acceptance_probability"])
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">🛵 Rider Acceptance</div>'
            f'<div class="result-value">{probability * 100:.1f}%</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    if result.get("rider_acceptance") == 1:
        st.markdown(
            '<span class="pill pill-ok">✅ Rider predicted to ACCEPT</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="pill pill-warn">⚠️ Rider predicted NOT to accept</span>',
            unsafe_allow_html=True,
        )

    weather = result.get("weather") or {}
    traffic = result.get("traffic") or {}

    with st.expander("🌤️ Weather & 🚦 traffic used for this prediction"):

        wc1, wc2, wc3, wc4 = st.columns(4)

        with wc1:
            st.metric("Condition", format_optional(weather.get("description")))
        with wc2:
            temperature = weather.get("temperature_c")
            st.metric(
                "Temperature",
                f"{temperature:.1f} °C" if temperature is not None else "N/A",
            )
        with wc3:
            humidity = weather.get("humidity_percent")
            st.metric(
                "Humidity",
                f"{humidity:.0f}%" if humidity is not None else "N/A",
            )
        with wc4:
            st.metric("Rainfall", f"{to_float(weather.get('rainfall_mm')):.1f} mm")

        tc1, tc2, tc3 = st.columns(3)

        with tc1:
            st.metric("Traffic Level", format_optional(traffic.get("traffic_level")))
        with tc2:
            st.metric("Traffic Index", f"{to_float(traffic.get('traffic_index')):.1f}")
        with tc3:
            st.metric("Current Speed", f"{to_float(traffic.get('current_speed_kmh')):.1f} km/h")

    st.caption("Powered by real-time weather and traffic data.")


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

# flow_state drives the mini state machine:
#   "awaiting_order_id"     -> next message is treated as an order ID
#   "awaiting_confirmation" -> next message is confirm/cancel/an edit
if "flow_state" not in st.session_state:
    st.session_state.flow_state = "awaiting_order_id"

# The order currently staged for confirmation: {"info": {...}, "payload": {...}}
if "pending_order" not in st.session_state:
    st.session_state.pending_order = None


def reset_chat():
    st.session_state.messages = []
    st.session_state.flow_state = "awaiting_order_id"
    st.session_state.pending_order = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="brand-row">'
        '<div class="brand-circle">⚡</div>'
        '<div><p class="brand-title">Zepto Smart</p>'
        '<p class="brand-sub">Commerce AI</p></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    if st.button("＋ New chat", use_container_width=True):
        reset_chat()
        st.rerun()

    st.markdown("#### Recent")
    if st.session_state.messages:
        user_turns = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
        for turn in user_turns[-5:][::-1]:
            first_line = turn.strip().splitlines()[0][:28] if turn.strip() else "Prediction"
            st.caption(f"💬 {first_line}…")
    else:
        st.caption("No conversations yet.")

    with st.expander("⚡ Capabilities"):
        st.write(
            "- Type an **order ID** and I'll pull that order's details\n"
            "- Review the details, then type **confirm** to run the "
            "delivery charge, ETA & rider-acceptance prediction\n"
            "- Not the right order? Type **cancel**, or just enter a "
            "different order ID\n"
            "- You can tweak a field before confirming — e.g. `distance_km: 5`\n"
            "- Live weather & traffic pulled server-side at prediction time\n"
            "- Sample order IDs: **ORD1001 – ORD1010**"
        )

    if st.session_state.pending_order:
        with st.expander("📋 Order awaiting confirmation", expanded=True):
            info = st.session_state.pending_order["info"]
            payload = st.session_state.pending_order["payload"]
            st.write(f"**{info.get('order_id')}** — {display_text(info.get('customer_name'))}")
            st.caption(display_text(info.get("product_name"), default=""))
            st.write(
                f"📍 {display_text(payload.get('city'))}  •  "
                f"📏 {to_float(payload.get('distance_km')):.1f} km  •  "
                f"💵 ₹{to_float(payload.get('order_amount')):.0f}"
            )

    status = get_service_status()
    state = status["state"]

    if state == "online":
        st.success("🟢 Service online")

    elif state == "degraded":
        st.warning(
            "🟡 Backend is reachable, but its health check reported a "
            "problem. Order lookup may still work."
        )

    elif state == "waking":
        st.warning(
            "🟡 Backend is waking up after being idle. "
            "This can take up to a minute."
        )

    else:
        st.error("🔴 Service unavailable — please try again shortly.")

    if state != "online":
        if status.get("detail"):
            st.caption(f"Details: {status['detail']}")

        if st.button("🔄 Check again", use_container_width=True):
            get_service_status(force=True)
            st.rerun()

    if st.button("🗑 Clear current chat", use_container_width=True):
        reset_chat()
        st.rerun()


# ============================================================
# HEADER (always visible)
# ============================================================

head_left, head_right = st.columns([0.88, 0.12], vertical_alignment="center")

with head_left:
    st.markdown(
        '<div class="brand-row">'
        '<div class="brand-circle">⚡</div>'
        '<div><p class="brand-title">Welcome to Zepto Smart Commerce AI</p>'
        '<p class="brand-sub">Delivery charge, ETA & rider-acceptance predictions</p></div>'
        "</div>",
        unsafe_allow_html=True,
    )

with head_right:
    st.button(
        "◐",
        key="theme_toggle",
        on_click=toggle_theme,
        help=(
            "Switch to light mode"
            if st.session_state.theme == "dark"
            else "Switch to dark mode"
        ),
    )

st.markdown("<br>", unsafe_allow_html=True)


# ============================================================
# EMPTY STATE
# ============================================================

if not st.session_state.messages:

    st.markdown(
        '<div class="welcome-wrap">'
        '<div class="brand-circle lg">⚡</div>'
        '<div class="welcome-title">Look up an order to get started</div>'
        '<div class="welcome-sub">Type an order ID - '
        "<code>ORDXXXX</code> — and I'll show you that order's details. "
        "Then just type <code>confirm</code> and I'll run the delivery "
        "charge, ETA & rider-acceptance prediction for it.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("See sample order IDs"):
        st.markdown(
            '<div class="example-box">'
            + "\n".join(f"ORD{1000 + i}" for i in range(1, 11))
            + "</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# CHAT HISTORY
# ============================================================

RENDERERS = {
    "order_found": render_order_found,
    "order_not_found": render_order_not_found,
    "cancelled": lambda content: render_cancelled(),
    "prediction": render_prediction_message,
}

for message in st.session_state.messages:

    avatar = "🧑" if message["role"] == "user" else "⚡"

    with st.chat_message(message["role"], avatar=avatar):

        if message["role"] == "user":
            st.markdown(message["content"])
            continue

        content = message["content"]
        msg_type = content.get("type")

        if msg_type == "error":
            st.error(content["message"])
        elif msg_type in RENDERERS:
            RENDERERS[msg_type](content)
        else:
            st.error("Something went wrong rendering this message.")


# ============================================================
# CHAT INPUT
# ============================================================

if st.session_state.flow_state == "awaiting_confirmation":
    placeholder = "Type 'confirm' to predict, 'cancel' to drop, or a new order ID…"
else:
    placeholder = "Enter an order ID, e.g. ORD1001…"

prompt = st.chat_input(placeholder)

if prompt:

    st.session_state.messages.append({"role": "user", "content": prompt})

    spinner_text = (
        "🤖 Generating prediction using HGB-v1..."
        if prompt.strip().lower() in CONFIRM_WORDS
        and st.session_state.flow_state == "awaiting_confirmation"
        else "🔎 Looking up order..."
    )

    with st.spinner(spinner_text):
        outcome = handle_user_message(prompt)

    st.session_state.messages.append({"role": "assistant", "content": outcome})

    st.rerun()

st.markdown(
    "<div style='text-align:center;'>Created by <b>Pearlraj</b></div>",
    unsafe_allow_html=True
)


# ============================================================
# DOCUMENT KNOWLEDGE ASSISTANT (separate from order prediction chat)
# ============================================================
st.divider()
with st.expander("📚 Ask the Document AI Assistant", expanded=False):
    st.caption("Answers are grounded in documents uploaded by the administrator.")
    if "document_chat_history" not in st.session_state:
        st.session_state.document_chat_history = []
    for item in st.session_state.document_chat_history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
    with st.form("document_assistant_form", clear_on_submit=True):
        doc_question = st.text_input("Your document question", max_chars=2000)
        doc_send = st.form_submit_button("Ask Document AI")
    if doc_send and doc_question.strip():
        try:
            result = requests.post(
                f"{API_BASE_URL.rstrip('/')}/rag/chat",
                json={"question": doc_question, "history": st.session_state.document_chat_history[-6:]},
                timeout=(10, 90),
            )
            result.raise_for_status()
            data = result.json()
            answer_text = data.get("answer", "No answer returned.")
            sources = sorted({x.get("filename", "") for x in data.get("sources", []) if x.get("filename")})
            if sources:
                answer_text += "\n\n**Sources:** " + ", ".join(sources)
            st.session_state.document_chat_history.extend([
                {"role": "user", "content": doc_question},
                {"role": "assistant", "content": answer_text},
            ])
            st.rerun()
        except requests.RequestException:
            st.error("Document assistant is unavailable. Verify the FastAPI service and uploaded documents.")
