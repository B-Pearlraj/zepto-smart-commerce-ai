import os
import re

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
    "http://127.0.0.1:8000",
)

api = APIClient(API_BASE_URL)


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
ZEPTO_INK = "#161119"
ZEPTO_GREEN = "#0CA750"
ZEPTO_PEACH = "#FFB74D"

st.markdown(
    f"""
    <style>

    /* Keep the header so the sidebar-collapse arrow (top-left) and the
       ☰ menu (Settings → Theme, for switching Light/Dark) stay usable.
       Only hide the "Made with Streamlit" footer and the Deploy button. */
    footer {{visibility: hidden;}}
    div[data-testid="stToolbarActions"] {{display: none;}}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}

    .stApp {{
        background: #FAF8FD;
        color: {ZEPTO_INK};
        font-family: "Poppins", "Segoe UI", sans-serif;
    }}

    /* The fixed bottom bar Streamlit wraps the chat input in defaults to
       the theme's base background; pin it to match our light theme so it
       doesn't show up as a stray black strip behind the input box. */
    div[data-testid="stBottom"] > div {{
        background: #FAF8FD;
    }}

    div[data-testid="stBottomBlockContainer"] {{
        background: #FAF8FD;
        padding-top: 8px;
    }}

    h1, h2, h3, .brand-title, .welcome-title {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        letter-spacing: -0.01em;
    }}

    section[data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid #EFE6FC;
    }}

    section[data-testid="stSidebar"] .stButton > button {{
        width: 100%;
        background: {ZEPTO_PURPLE};
        color: #FFFFFF;
        border: none;
        border-radius: 999px;
        font-weight: 700;
        text-align: center;
        padding: 10px 16px;
        box-shadow: 0 4px 14px rgba(139, 47, 248, 0.28);
    }}

    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: {ZEPTO_PURPLE_DARK};
        color: #FFFFFF;
    }}

    section[data-testid="stSidebar"] div[data-testid="stExpander"] {{
        border: 1px solid #EFE6FC;
        border-radius: 12px;
        background: #FDFBFF;
    }}

    .brand-row {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 4px;
    }}

    .brand-circle {{
        width: 36px;
        height: 36px;
        border-radius: 11px;
        background: {ZEPTO_PURPLE};
        box-shadow: 0 4px 14px rgba(139, 47, 248, 0.35);
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
    }}

    .brand-circle.lg {{
        width: 84px;
        height: 84px;
        border-radius: 24px;
        margin: 0 auto 18px auto;
        font-size: 40px;
    }}

    .brand-title {{
        font-size: 19px;
        font-weight: 800;
        color: {ZEPTO_INK};
        margin: 0;
    }}

    .brand-sub {{
        font-size: 12.5px;
        color: #7A6E88;
        margin: 0;
    }}

    .welcome-wrap {{
        text-align: center;
        margin-top: 7vh;
    }}

    .welcome-title {{
        font-size: 28px;
        font-weight: 800;
        color: {ZEPTO_INK};
        margin-bottom: 6px;
    }}

    .welcome-sub {{
        font-size: 15px;
        color: #7A6E88;
        max-width: 580px;
        margin: 0 auto;
    }}

    .welcome-sub code {{
        background: #F1E6FE;
        color: {ZEPTO_PURPLE_DARK};
        padding: 1px 6px;
        border-radius: 6px;
    }}

    .example-box {{
        background: #FFFFFF;
        border: 1px solid #EFE6FC;
        border-radius: 14px;
        padding: 14px 16px;
        font-family: "SFMono-Regular", Consolas, monospace;
        font-size: 12.5px;
        color: #56495F;
        max-height: 220px;
        overflow-y: auto;
        text-align: left;
        margin-top: 22px;
        box-shadow: 0 2px 10px rgba(139, 47, 248, 0.06);
    }}

    div[data-testid="stChatMessage"] {{
        background: #FFFFFF;
        border: 1px solid #EFE6FC;
        border-radius: 16px;
        padding: 6px 8px;
        box-shadow: 0 2px 10px rgba(139, 47, 248, 0.05);
    }}

    .result-card {{
        background: #FBF7FF;
        border: 1px solid #EFE6FC;
        border-radius: 14px;
        padding: 14px 16px;
        text-align: center;
    }}

    .result-label {{
        color: #7A6E88;
        font-size: 12.5px;
        font-weight: 600;
        margin-bottom: 4px;
    }}

    .result-value {{
        color: {ZEPTO_PURPLE_DARK};
        font-size: 22px;
        font-weight: 800;
    }}

    .pill {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12.5px;
        font-weight: 700;
    }}

    .pill-ok {{ background: rgba(12, 167, 80, 0.12); color: {ZEPTO_GREEN}; }}
    .pill-warn {{ background: rgba(255, 183, 77, 0.18); color: #B9720A; }}

    .diff-row {{
        font-size: 12.5px;
        color: #56495F;
        font-family: "SFMono-Regular", Consolas, monospace;
        margin-bottom: 2px;
    }}

    .diff-key {{ color: {ZEPTO_PURPLE_DARK}; font-weight: 650; }}
    .diff-old {{ color: #A79BB3; text-decoration: line-through; }}
    .diff-new {{ color: {ZEPTO_GREEN}; font-weight: 700; }}

    div[data-testid="stChatInput"] {{
        background: #FFFFFF;
        border: 1px solid #EFE6FC;
        border-radius: 999px;
        box-shadow: 0 2px 10px rgba(139, 47, 248, 0.06);
        max-width: 900px;
        margin: 0 auto;
    }}

    div[data-testid="stChatInput"] textarea {{
        background: #FFFFFF !important;
        color: {ZEPTO_INK} !important;
    }}

    div[data-testid="stChatInput"] textarea::placeholder {{
        color: #A79BB3 !important;
        opacity: 1 !important;
    }}

    .stButton > button[kind="primary"], button[data-testid="stChatInputSubmitButton"] {{
        background: {ZEPTO_PURPLE} !important;
        border-color: {ZEPTO_PURPLE} !important;
    }}

    button[data-testid="stChatInputSubmitButton"] svg {{
        fill: #FFFFFF !important;
    }}

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PARSING HELPERS
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
    except Exception as exc:
        return {
            "type": "error",
            "message": f"Couldn't reach the order lookup service: {exc}",
        }

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
        f"{info.get('customer_name', 'N/A')}"
    )
    st.markdown(
        f"🛒 {info.get('product_name', 'N/A')}  •  "
        f"Status: `{info.get('order_status', 'N/A')}`"
    )

    st.markdown("")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">📍 City</div>'
            f'<div class="result-value" style="font-size:18px;">{info.get("city", "N/A")}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">📏 Distance</div>'
            f'<div class="result-value" style="font-size:18px;">{info.get("distance_km", 0):.1f} km</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            '<div class="result-card">'
            '<div class="result-label">💵 Order Amount</div>'
            f'<div class="result-value" style="font-size:18px;">₹{info.get("order_amount", 0):.0f}</div>'
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
        f"({info.get('customer_name', 'N/A')}, {info.get('product_name', 'N/A')})."
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

    weather = result.get("weather", {})
    traffic = result.get("traffic", {})

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
            st.metric("Rainfall", f"{weather.get('rainfall_mm', 0):.1f} mm")

        tc1, tc2, tc3 = st.columns(3)

        with tc1:
            st.metric("Traffic Level", format_optional(traffic.get("traffic_level")))
        with tc2:
            st.metric("Traffic Index", f"{traffic.get('traffic_index', 0):.1f}")
        with tc3:
            st.metric("Current Speed", f"{traffic.get('current_speed_kmh', 0):.1f} km/h")

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
            st.write(f"**{info.get('order_id')}** — {info.get('customer_name', 'N/A')}")
            st.caption(info.get("product_name", ""))
            st.write(f"📍 {payload.get('city', 'N/A')}  •  📏 {payload.get('distance_km', 0):.1f} km  •  💵 ₹{payload.get('order_amount', 0):.0f}")

    try:
        api.health_check()
        st.success("🟢 Service online")
    except Exception:
        st.error("🔴 Service unavailable — please try again shortly.")

    if st.button("🗑 Clear current chat", use_container_width=True):
        reset_chat()
        st.rerun()


# ============================================================
# HEADER (always visible)
# ============================================================

st.markdown(
    '<div class="brand-row">'
    '<div class="brand-circle">⚡</div>'
    '<div><p class="brand-title">Welcome to Zepto Smart Commerce AI</p>'
    '<p class="brand-sub">Delivery charge, ETA & rider-acceptance predictions</p></div>'
    "</div>",
    unsafe_allow_html=True,
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
