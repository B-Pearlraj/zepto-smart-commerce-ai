import datetime
import os

import streamlit as st

from api_client import APIClient


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Zepto Smart Commerce AI",
    page_icon="🛵",
    layout="wide",
    initial_sidebar_state="collapsed",
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
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --zc-primary: #6D28D9;
        --zc-primary-dark: #5B21B6;
        --zc-accent: #EC4899;
        --zc-ink: #1E1B2E;
        --zc-muted: #6B7280;
        --zc-border: #ECE9F5;
        --zc-surface: #FFFFFF;
        --zc-surface-soft: #FAF9FF;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(109,40,217,0.06), transparent 40%),
            radial-gradient(circle at 90% 10%, rgba(236,72,153,0.06), transparent 40%),
            #FBFAFE;
    }

    /* ---------- HEADER ---------- */

    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-top: 6px;
        margin-bottom: 6px;
        background: linear-gradient(90deg, var(--zc-primary) 0%, var(--zc-accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .subtitle {
        text-align: center;
        color: var(--zc-muted);
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 34px;
    }

    /* ---------- SECTION TITLES ---------- */

    .section-title {
        font-size: 19px;
        font-weight: 700;
        color: var(--zc-ink);
        margin-top: 6px;
        margin-bottom: 14px;
        padding-left: 12px;
        border-left: 4px solid var(--zc-primary);
    }

    /* ---------- CONTAINERS / "CARD" SECTIONS ---------- */

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--zc-surface);
        border-radius: 16px !important;
        border: 1px solid var(--zc-border) !important;
        box-shadow: 0 4px 20px rgba(109, 40, 217, 0.05);
        padding: 6px 4px;
        margin-bottom: 6px;
    }

    /* ---------- INPUTS ---------- */

    .stTextInput input,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stDateInput input {
        border-radius: 10px !important;
        border: 1px solid var(--zc-border) !important;
        background: var(--zc-surface-soft) !important;
    }

    .stTextInput input:focus,
    .stNumberInput input:focus {
        border-color: var(--zc-primary) !important;
        box-shadow: 0 0 0 1px var(--zc-primary) !important;
    }

    label, .stMarkdown p strong {
        color: var(--zc-ink) !important;
        font-weight: 600 !important;
    }

    /* ---------- PREDICTION RESULT CARDS ---------- */

    .prediction-card {
        background: linear-gradient(180deg, var(--zc-surface) 0%, var(--zc-surface-soft) 100%);
        border: 1px solid var(--zc-border);
        border-top: 4px solid var(--zc-primary);
        border-radius: 16px;
        padding: 24px;
        min-height: 145px;
        box-shadow: 0 6px 24px rgba(109, 40, 217, 0.08);
        transition: transform 0.15s ease;
    }

    .prediction-card:hover {
        transform: translateY(-2px);
    }

    .prediction-label {
        color: var(--zc-muted);
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 8px;
    }

    .prediction-value {
        font-size: 32px;
        font-weight: 800;
        color: var(--zc-ink);
    }

    /* ---------- LIVE DATA CARDS ---------- */

    .live-card {
        background: var(--zc-surface);
        border: 1px solid var(--zc-border);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 4px 16px rgba(109, 40, 217, 0.05);
    }

    div[data-testid="stMetric"] {
        background: var(--zc-surface-soft);
        border: 1px solid var(--zc-border);
        border-radius: 12px;
        padding: 12px 14px;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--zc-muted) !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--zc-ink) !important;
        font-weight: 700 !important;
    }

    /* ---------- BUTTONS ---------- */

    .stButton > button {
        font-weight: 700;
        border-radius: 12px !important;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, var(--zc-primary) 0%, var(--zc-accent) 100%) !important;
        border: none !important;
        box-shadow: 0 8px 20px rgba(109, 40, 217, 0.25);
        font-size: 16px;
        padding: 0.6em 0;
    }

    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 10px 26px rgba(109, 40, 217, 0.35);
    }

    /* ---------- SIDEBAR ---------- */

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F5F2FE 0%, #FBFAFE 100%);
        border-right: 1px solid var(--zc-border);
    }

    /* ---------- ALERTS / INFO BOXES ---------- */

    div[data-testid="stAlertContainer"] {
        border-radius: 12px !important;
    }

    /* ---------- DIVIDER ---------- */

    hr {
        border-color: var(--zc-border) !important;
    }

    /* ---------- CAPTION / FOOTER ---------- */

    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--zc-muted) !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def distance_band(distance):
    if distance <= 2:
        return "0-2"
    elif distance <= 5:
        return "2-5"
    elif distance <= 10:
        return "5-10"
    elif distance <= 20:
        return "10-20"
    return "20+"


def amount_band(amount):
    if amount < 300:
        return "low"
    elif amount <= 1000:
        return "medium"
    return "high"


def experience_band(months):
    if months < 3:
        return "new"
    elif months < 12:
        return "beginner"
    elif months < 24:
        return "intermediate"
    return "experienced"


def rating_band(rating):
    if rating < 3:
        return "low"
    elif rating < 4:
        return "medium"
    return "high"


def time_of_day(hour):
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    return "night"


def is_peak_hour(hour):
    return int(
        hour in [8, 9, 10, 18, 19, 20, 21]
    )


def format_optional(value):
    if value is None:
        return "N/A"
    return str(value)


def reset_prediction():
    st.session_state.prediction = None


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🛵 Zepto Smart Commerce AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "AI-powered Delivery Charge, ETA & Rider Acceptance Prediction"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ System Status")

    try:

        health = api.health_check()

        st.success("FastAPI Connected")

        st.write(
            f"**Model:** "
            f"{health.get('model_version', 'N/A')}"
        )

        st.write(
            f"**Weather:** "
            f"{health.get('weather_provider', 'N/A')}"
        )

        st.write(
            f"**Traffic:** "
            f"{health.get('traffic_provider', 'N/A')}"
        )

        st.divider()

        st.caption(
            "Weather and traffic are automatically "
            "obtained by the FastAPI backend."
        )

    except Exception as exc:

        st.error("FastAPI is not connected.")

        st.caption(str(exc))


# ============================================================
# PREDICTION FORM
# ============================================================

st.markdown(
    '<div class="section-title">'
    "📦 Customer & Delivery"
    "</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):

    c1, c2, c3 = st.columns(3)

    with c1:

        city = st.text_input(
            "City",
            value="Chennai",
        )

    with c2:

        city_tier = st.selectbox(
            "City Tier",
            [1, 2, 3],
            index=0,
        )

    with c3:

        delivery_zone = st.selectbox(
            "Delivery Zone",
            [
                "urban",
                "suburban",
                "rural",
            ],
        )

    c1, c2 = st.columns(2)

    with c1:

        st.markdown("**Customer Location**")

        customer_lat = st.number_input(
            "Customer Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=13.0827,
            format="%.6f",
        )

    with c2:

        st.markdown("**Customer Location**")

        customer_lon = st.number_input(
            "Customer Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=80.2707,
            format="%.6f",
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        distance_km = st.number_input(
            "Delivery Distance (km)",
            min_value=0.0,
            value=1.8,
            format="%.2f",
        )

    with c2:

        service_radius_km = st.number_input(
            "Service Radius (km)",
            min_value=0.1,
            value=10.0,
            format="%.2f",
        )

    with c3:

        within_radius = st.selectbox(
            "Within Service Radius?",
            ["Yes", "No"],
        )


# ============================================================
# STORE & ORDER
# ============================================================

st.markdown(
    '<div class="section-title">'
    "🏪 Store & Order"
    "</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):

    c1, c2, c3 = st.columns(3)

    with c1:

        store_id = st.text_input(
            "Store ID",
            value="DS001",
        )

    with c2:

        store_lat = st.number_input(
            "Store Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=13.0800,
            format="%.6f",
        )

    with c3:

        store_lon = st.number_input(
            "Store Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=80.2700,
            format="%.6f",
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        item_count = st.number_input(
            "Item Count",
            min_value=0,
            value=5,
            step=1,
        )

    with c2:

        order_amount = st.number_input(
            "Order Amount (₹)",
            min_value=0.0,
            value=450.0,
            format="%.2f",
        )

    with c3:

        order_weight = st.number_input(
            "Order Weight (kg)",
            min_value=0.01,
            value=2.0,
            format="%.2f",
        )


# ============================================================
# RIDER DETAILS
# ============================================================

st.markdown(
    '<div class="section-title">'
    "🛵 Rider Details"
    "</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        rider_experience = st.number_input(
            "Experience (months)",
            min_value=0.0,
            value=24.0,
            format="%.1f",
        )

    with c2:

        rider_rating = st.number_input(
            "Rider Rating",
            min_value=0.0,
            max_value=5.0,
            value=4.7,
            format="%.1f",
        )

    with c3:

        vehicle_type = st.selectbox(
            "Vehicle Type",
            [
                "bike",
                "scooter",
                "ev_bike",
                "bicycle",
            ],
        )

    with c4:

        current_rider_load = st.number_input(
            "Current Rider Load",
            min_value=0.0,
            value=2.0,
            format="%.1f",
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        previous_acceptance_rate = st.number_input(
            "Previous Acceptance Rate",
            min_value=0.0,
            max_value=1.0,
            value=0.85,
            format="%.2f",
        )

    with c2:

        rider_earnings_today = st.number_input(
            "Today's Rider Earnings (₹)",
            min_value=0.0,
            value=850.0,
            format="%.2f",
        )

    with c3:

        current_incentive = st.number_input(
            "Current Incentive (₹)",
            min_value=0.0,
            value=20.0,
            format="%.2f",
        )


# ============================================================
# ORDER CONTEXT
# ============================================================

st.markdown(
    '<div class="section-title">'
    "📅 Order Context"
    "</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        order_date = st.date_input(
            "Order Date",
            value=datetime.date(2026, 9, 8),
        )

    with c2:

        order_hour = st.number_input(
            "Order Hour (0–23)",
            min_value=0,
            max_value=23,
            value=14,
            step=1,
        )

    with c3:

        road_type = st.selectbox(
            "Road Type",
            [
                "main_road",
                "side_road",
                "residential",
                "highway",
                "service_road",
            ],
        )

    with c4:

        membership_type = st.selectbox(
            "Membership",
            [
                "regular",
                "pass",
                "pass_plus",
            ],
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        demand_level = st.selectbox(
            "Demand Level",
            [
                "low",
                "medium",
                "high",
            ],
            index=1,
        )

    with c2:

        festival_day = st.selectbox(
            "Festival Day",
            [
                "No",
                "Yes",
            ],
        )

    with c3:

        historical_delivery_cost = st.number_input(
            "Historical Delivery Cost (₹)",
            min_value=0.0,
            value=48.0,
            format="%.2f",
        )

    historical_travel_time = st.number_input(
        "Historical Travel Time (minutes)",
        min_value=0.0,
        value=18.0,
        format="%.2f",
    )


# ============================================================
# LIVE DATA NOTICE
# ============================================================

st.info(
    "🌤️ **Weather:** Automatically fetched LIVE from OpenWeather  "
    "  🚦 **Traffic:** Automatically fetched LIVE from TomTom"
)


# ============================================================
# PREDICT BUTTON
# ============================================================

st.markdown("")

predict_button = st.button(
    "🚀 PREDICT DELIVERY",
    type="primary",
    use_container_width=True,
)


# ============================================================
# PREDICTION
# ============================================================

if predict_button:

    try:

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not city.strip():

            st.error(
                "Please enter a city."
            )

            st.stop()

        if not store_id.strip():

            st.error(
                "Please enter a store ID."
            )

            st.stop()

        if distance_km < 0:

            st.error(
                "Delivery distance cannot be negative."
            )

            st.stop()

        if service_radius_km <= 0:

            st.error(
                "Service radius must be greater than zero."
            )

            st.stop()

        if order_weight <= 0:

            st.error(
                "Order weight must be greater than zero."
            )

            st.stop()

        # ----------------------------------------------------
        # DERIVED FEATURES
        # ----------------------------------------------------

        ratio = (
            distance_km / service_radius_km
        )

        within_service_radius = (
            1
            if within_radius == "Yes"
            else 0
        )

        calculated_distance_band = (
            distance_band(distance_km)
        )

        calculated_amount_band = (
            amount_band(order_amount)
        )

        calculated_amount_per_kg = (
            order_amount / order_weight
        )

        calculated_experience_band = (
            experience_band(
                rider_experience
            )
        )

        calculated_rating_band = (
            rating_band(
                rider_rating
            )
        )

        calculated_time_of_day = (
            time_of_day(
                order_hour
            )
        )

        calculated_peak_hour = (
            is_peak_hour(
                order_hour
            )
        )

        calculated_weekend = int(
            order_date.weekday() >= 5
        )

        calculated_month_start = int(
            order_date.day == 1
        )

        calculated_month_end = int(
            order_date.day
            == (
                order_date.replace(
                    day=28
                )
                + datetime.timedelta(
                    days=4
                )
            ).replace(
                day=1
            )
            - datetime.timedelta(
                days=1
            )
        )

        # ----------------------------------------------------
        # API PAYLOAD
        # ----------------------------------------------------

        payload = {

            "city": city.strip(),

            "city_tier": int(city_tier),

            "customer_lat": float(
                customer_lat
            ),

            "customer_lon": float(
                customer_lon
            ),

            "store_id": store_id.strip(),

            "store_lat": float(
                store_lat
            ),

            "store_lon": float(
                store_lon
            ),

            "delivery_zone": delivery_zone,

            "distance_km": float(
                distance_km
            ),

            "distance_band":
                calculated_distance_band,

            "distance_to_radius_ratio":
                round(
                    ratio,
                    4,
                ),

            "service_radius_km":
                float(
                    service_radius_km
                ),

            "within_service_radius":
                within_service_radius,

            "item_count":
                int(item_count),

            "order_amount":
                float(order_amount),

            "order_amount_band":
                calculated_amount_band,

            "order_weight_kg":
                float(order_weight),

            "order_amount_per_kg":
                round(
                    calculated_amount_per_kg,
                    4,
                ),

            "order_year":
                int(order_date.year),

            "order_month":
                int(order_date.month),

            "order_day":
                int(order_date.day),

            "order_hour":
                int(order_hour),

            "order_dayofweek":
                int(order_date.weekday()),

            "is_month_start":
                calculated_month_start,

            "is_month_end":
                calculated_month_end,

            "is_peak_hour":
                calculated_peak_hour,

            "is_weekend":
                calculated_weekend,

            "time_of_day":
                calculated_time_of_day,

            # ------------------------------------------------
            # WEATHER PLACEHOLDERS
            #
            # FastAPI replaces these with LIVE OpenWeather
            # values before prediction.
            # ------------------------------------------------

            "weather_condition": "clear",

            "weather_severity": 0,

            "rainfall_mm": 0.0,

            "has_rain": 0,

            # ------------------------------------------------
            # TRAFFIC PLACEHOLDERS
            #
            # FastAPI replaces these with LIVE TomTom
            # values before prediction.
            # ------------------------------------------------

            "traffic_index": 0.0,

            "traffic_level": "low",

            "road_type": road_type,

            "current_rider_load":
                float(
                    current_rider_load
                ),

            "previous_acceptance_rate":
                float(
                    previous_acceptance_rate
                ),

            "rider_earnings_today":
                float(
                    rider_earnings_today
                ),

            "rider_experience_months":
                float(
                    rider_experience
                ),

            "rider_experience_band":
                calculated_experience_band,

            "rider_rating":
                float(
                    rider_rating
                ),

            "rider_rating_band":
                calculated_rating_band,

            "vehicle_type":
                vehicle_type,

            "current_incentive":
                float(
                    current_incentive
                ),

            "membership_type":
                membership_type,

            "historical_delivery_cost":
                float(
                    historical_delivery_cost
                ),

            "historical_travel_time":
                float(
                    historical_travel_time
                ),

            "demand_level":
                demand_level,

            "festival_day_flag":
                1
                if festival_day == "Yes"
                else 0,
        }

        # ----------------------------------------------------
        # API CALL
        # ----------------------------------------------------

        with st.spinner(
            "🤖 Generating prediction using HGB-v1..."
        ):

            result = api.predict(
                payload
            )

        st.session_state.prediction = result

    except Exception as exc:

        st.error(
            "Prediction failed."
        )

        st.code(
            str(exc)
        )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.get(
    "prediction"
):

    result = st.session_state.prediction

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        "🎯 Prediction Results"
        "</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # MAIN RESULTS
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            '<div class="prediction-card">',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="prediction-label">'
            "💰 Delivery Charge"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="prediction-value">'
            f'₹{result["delivery_charge"]:.2f}'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

    with c2:

        st.markdown(
            '<div class="prediction-card">',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="prediction-label">'
            "⏱️ Estimated Delivery Time"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="prediction-value">'
            f'{result["delivery_time_minutes"]:.1f} min'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

    with c3:

        probability = float(
            result[
                "rider_acceptance_probability"
            ]
        )

        st.markdown(
            '<div class="prediction-card">',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="prediction-label">'
            "🛵 Rider Acceptance"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="prediction-value">'
            f'{probability * 100:.1f}%'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")

    if result["rider_acceptance"] == 1:

        st.success(
            "✅ Rider is predicted to ACCEPT the order."
        )

    else:

        st.warning(
            "⚠️ Rider is predicted NOT to accept the order."
        )

    # --------------------------------------------------------
    # LIVE WEATHER
    # --------------------------------------------------------

    weather = result.get(
        "weather",
        {},
    )

    st.markdown(
        '<div class="section-title">'
        "🌤️ Live Weather Used for Prediction"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Condition",
                format_optional(
                    weather.get(
                        "description"
                    )
                ),
            )

        with c2:

            temperature = weather.get(
                "temperature_c"
            )

            st.metric(
                "Temperature",
                (
                    f"{temperature:.1f} °C"
                    if temperature is not None
                    else "N/A"
                ),
            )

        with c3:

            humidity = weather.get(
                "humidity_percent"
            )

            st.metric(
                "Humidity",
                (
                    f"{humidity:.0f}%"
                    if humidity is not None
                    else "N/A"
                ),
            )

        with c4:

            rainfall = weather.get(
                "rainfall_mm",
                0,
            )

            st.metric(
                "Rainfall",
                f"{rainfall:.1f} mm",
            )

        st.write(
            f"**Location:** "
            f"{format_optional(weather.get('location_name'))}"
        )

        st.write(
            f"**ML Weather Category:** "
            f"{format_optional(weather.get('weather_condition'))}"
        )

        st.write(
            f"**Source:** "
            f"`{format_optional(weather.get('source'))}`"
        )

    # --------------------------------------------------------
    # LIVE TRAFFIC
    # --------------------------------------------------------

    traffic = result.get(
        "traffic",
        {},
    )

    st.markdown(
        '<div class="section-title">'
        "🚦 Live Traffic Used for Prediction"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Traffic Level",
                format_optional(
                    traffic.get(
                        "traffic_level"
                    )
                ),
            )

        with c2:

            st.metric(
                "Traffic Index",
                f'{traffic.get("traffic_index", 0):.1f}',
            )

        with c3:

            st.metric(
                "Current Speed",
                f'{traffic.get("current_speed_kmh", 0):.1f} km/h',
            )

        with c4:

            st.metric(
                "Free Flow Speed",
                f'{traffic.get("free_flow_speed_kmh", 0):.1f} km/h',
            )

        st.write(
            f"**Source:** "
            f"`{format_optional(traffic.get('source'))}`"
        )

    # --------------------------------------------------------
    # MODEL INFORMATION
    # --------------------------------------------------------

    st.markdown("")

    st.info(
        f"Model Version: **{result.get('model_version', 'HGB-v1')}** "
        "• Live weather and traffic were obtained by FastAPI "
        "• Prediction recorded in PostgreSQL audit."
    )

    if st.button(
        "🔄 New Prediction",
        use_container_width=True,
    ):

        reset_prediction()
        st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "Zepto Smart Commerce AI Platform • "
    "HGB-v1 • Live OpenWeather • Live TomTom Traffic • PostgreSQL"
)
