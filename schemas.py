"""
Pydantic request and response schemas
for the Zepto Smart Commerce AI Platform.

Model Version: HGB-v1
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ======================================================================
# REQUEST SCHEMA
# ======================================================================

class DeliveryPredictionRequest(BaseModel):
    """
    Input schema for the production delivery intelligence API.

    The API receives the core order/rider/context information required
    by the three production ML models.

    All prediction fields are required at the API boundary.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    # ------------------------------------------------------------------
    # Order / distance
    # ------------------------------------------------------------------

    distance_km: float = Field(
        ...,
        description="Delivery distance in kilometres."
    )

    distance_band: str = Field(
        ...,
        description="Engineered delivery distance category."
    )

    distance_to_radius_ratio: float = Field(
        ...,
        description="Distance divided by store service radius."
    )

    within_service_radius: int = Field(
        ...,
        description="Whether the order is within the store service radius."
    )

    service_radius_km: float = Field(
        ...,
        description="Store service radius in kilometres."
    )

    # ------------------------------------------------------------------
    # Order information
    # ------------------------------------------------------------------

    order_amount: float = Field(
        ...,
        description="Order value."
    )

    order_amount_band: str = Field(
        ...,
        description="Engineered order amount category."
    )

    order_amount_per_kg: float = Field(
        ...,
        description="Order amount per kilogram."
    )

    order_weight_kg: float = Field(
        ...,
        description="Order weight in kilograms."
    )

    item_count: float = Field(
        ...,
        description="Number of items in the order."
    )

    # ------------------------------------------------------------------
    # Store / customer location
    # ------------------------------------------------------------------

    store_id: str = Field(
        ...,
        description="Dark store identifier."
    )

    store_lat: float = Field(
        ...,
        description="Store latitude."
    )

    store_lon: float = Field(
        ...,
        description="Store longitude."
    )

    customer_lat: float = Field(
        ...,
        description="Customer latitude."
    )

    customer_lon: float = Field(
        ...,
        description="Customer longitude."
    )

    delivery_zone: str = Field(
        ...,
        description="Delivery zone."
    )

    city: str = Field(
        ...,
        description="City."
    )

    city_tier: int = Field(
        ...,
        description="City tier."
    )

    # ------------------------------------------------------------------
    # Traffic / weather / road
    # ------------------------------------------------------------------

    traffic_index: float = Field(
        ...,
        description="Traffic index."
    )

    traffic_level: str = Field(
        ...,
        description="Traffic category."
    )

    weather_condition: str = Field(
        ...,
        description="Weather condition."
    )

    weather_severity: float = Field(
        ...,
        description="Weather severity score."
    )

    rainfall_mm: float = Field(
        ...,
        description="Rainfall in millimetres."
    )

    has_rain: int = Field(
        ...,
        description="Rain indicator."
    )

    road_type: str = Field(
        ...,
        description="Road category."
    )

    # ------------------------------------------------------------------
    # Rider information
    # ------------------------------------------------------------------

    vehicle_type: str = Field(
        ...,
        description="Normalized vehicle type."
    )

    rider_experience_months: float = Field(
        ...,
        description="Rider experience in months."
    )

    rider_experience_band: str = Field(
        ...,
        description="Rider experience category."
    )

    rider_rating: float = Field(
        ...,
        description="Rider rating."
    )

    rider_rating_band: str = Field(
        ...,
        description="Rider rating category."
    )

    rider_earnings_today: float = Field(
        ...,
        description="Rider earnings for the current day."
    )

    current_rider_load: float = Field(
        ...,
        description="Current rider workload."
    )

    previous_acceptance_rate: float = Field(
        ...,
        description="Historical rider acceptance rate."
    )

    current_incentive: float = Field(
        ...,
        description="Current delivery/rider incentive."
    )

    # ------------------------------------------------------------------
    # Demand / membership
    # ------------------------------------------------------------------

    demand_level: str = Field(
        ...,
        description="Demand category."
    )

    membership_type: str = Field(
        ...,
        description="Customer membership type."
    )

    # ------------------------------------------------------------------
    # Time / calendar
    # ------------------------------------------------------------------

    order_year: int = Field(
        ...,
        description="Order year."
    )

    order_month: int = Field(
        ...,
        description="Order month."
    )

    order_day: int = Field(
        ...,
        description="Order day."
    )

    order_hour: int = Field(
        ...,
        description="Order hour."
    )

    order_dayofweek: int = Field(
        ...,
        description="Day of week."
    )

    time_of_day: str = Field(
        ...,
        description="Time-of-day category."
    )

    is_peak_hour: int = Field(
        ...,
        description="Peak-hour indicator."
    )

    is_weekend: int = Field(
        ...,
        description="Weekend indicator."
    )

    is_month_start: int = Field(
        ...,
        description="Month-start indicator."
    )

    is_month_end: int = Field(
        ...,
        description="Month-end indicator."
    )

    festival_day_flag: int = Field(
        ...,
        description="Festival-day indicator."
    )

    # ------------------------------------------------------------------
    # Historical information
    # ------------------------------------------------------------------

    historical_delivery_cost: float = Field(
        ...,
        description="Historical delivery cost."
    )

    historical_travel_time: float = Field(
        ...,
        description="Historical travel time."
    )

    # ==================================================================
    # VALIDATION RULES
    # ==================================================================

    @field_validator("distance_km")
    @classmethod
    def validate_distance_km(cls, value):
        if value < 0:
            raise ValueError(
                "distance_km must be greater than or equal to 0"
            )
        return value

    @field_validator("distance_to_radius_ratio")
    @classmethod
    def validate_distance_ratio(cls, value):
        if value < 0:
            raise ValueError(
                "distance_to_radius_ratio must be greater than or equal to 0"
            )
        return value

    @field_validator("service_radius_km")
    @classmethod
    def validate_service_radius(cls, value):
        if value < 0:
            raise ValueError(
                "service_radius_km must be greater than or equal to 0"
            )
        return value

    @field_validator("order_amount")
    @classmethod
    def validate_order_amount(cls, value):
        if value < 0:
            raise ValueError(
                "order_amount must be greater than or equal to 0"
            )
        return value

    @field_validator("order_amount_per_kg")
    @classmethod
    def validate_order_amount_per_kg(cls, value):
        if value < 0:
            raise ValueError(
                "order_amount_per_kg must be greater than or equal to 0"
            )
        return value

    @field_validator("order_weight_kg")
    @classmethod
    def validate_order_weight(cls, value):
        if value < 0:
            raise ValueError(
                "order_weight_kg must be greater than or equal to 0"
            )
        return value

    @field_validator("item_count")
    @classmethod
    def validate_item_count(cls, value):
        if value < 0:
            raise ValueError(
                "item_count must be greater than or equal to 0"
            )
        return value

    @field_validator("traffic_index")
    @classmethod
    def validate_traffic_index(cls, value):
        if value < 0:
            raise ValueError(
                "traffic_index must be greater than or equal to 0"
            )
        if value > 100:
            raise ValueError(
                "traffic_index must be less than or equal to 100"
            )
        return value

    @field_validator("rainfall_mm")
    @classmethod
    def validate_rainfall(cls, value):
        if value < 0:
            raise ValueError(
                "rainfall_mm must be greater than or equal to 0"
            )
        return value

    @field_validator("rider_experience_months")
    @classmethod
    def validate_rider_experience(cls, value):
        if value < 0:
            raise ValueError(
                "rider_experience_months must be greater than or equal to 0"
            )
        return value

    @field_validator("rider_rating")
    @classmethod
    def validate_rider_rating(cls, value):
        if not 0 <= value <= 5:
            raise ValueError(
                "rider_rating must be between 0 and 5"
            )
        return value

    @field_validator("previous_acceptance_rate")
    @classmethod
    def validate_acceptance_rate(cls, value):
        if not 0 <= value <= 1:
            raise ValueError(
                "previous_acceptance_rate must be between 0 and 1"
            )
        return value

    @field_validator("within_service_radius")
    @classmethod
    def validate_within_service_radius(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "within_service_radius must be either 0 or 1"
            )
        return value

    @field_validator("has_rain")
    @classmethod
    def validate_has_rain(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "has_rain must be either 0 or 1"
            )
        return value

    @field_validator("is_peak_hour")
    @classmethod
    def validate_peak_hour(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "is_peak_hour must be either 0 or 1"
            )
        return value

    @field_validator("is_weekend")
    @classmethod
    def validate_weekend(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "is_weekend must be either 0 or 1"
            )
        return value

    @field_validator("is_month_start")
    @classmethod
    def validate_month_start(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "is_month_start must be either 0 or 1"
            )
        return value

    @field_validator("is_month_end")
    @classmethod
    def validate_month_end(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "is_month_end must be either 0 or 1"
            )
        return value

    @field_validator("festival_day_flag")
    @classmethod
    def validate_festival_day(cls, value):
        if value not in (0, 1):
            raise ValueError(
                "festival_day_flag must be either 0 or 1"
            )
        return value

    @field_validator("order_month")
    @classmethod
    def validate_order_month(cls, value):
        if not 1 <= value <= 12:
            raise ValueError(
                "order_month must be between 1 and 12"
            )
        return value

    @field_validator("order_day")
    @classmethod
    def validate_order_day(cls, value):
        if not 1 <= value <= 31:
            raise ValueError(
                "order_day must be between 1 and 31"
            )
        return value

    @field_validator("order_hour")
    @classmethod
    def validate_order_hour(cls, value):
        if not 0 <= value <= 23:
            raise ValueError(
                "order_hour must be between 0 and 23"
            )
        return value

    @field_validator("order_dayofweek")
    @classmethod
    def validate_order_dayofweek(cls, value):
        if not 0 <= value <= 6:
            raise ValueError(
                "order_dayofweek must be between 0 and 6"
            )
        return value


# ======================================================================
# RESPONSE SCHEMA
# ======================================================================

class LiveWeatherResponse(BaseModel):
    """
    Current live weather returned by OpenWeather.
    """

    source: str
    location_name: str | None = None

    weather_condition: str
    description: str

    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: float | None = None
    pressure_hpa: float | None = None

    rainfall_mm: float
    has_rain: int
    weather_severity: int


class LiveTrafficResponse(BaseModel):
    """
    Current live traffic returned by TomTom.
    """

    source: str

    current_speed_kmh: float
    free_flow_speed_kmh: float

    traffic_index: float
    traffic_level: str


class DeliveryPredictionResponse(BaseModel):
    """
    Complete live prediction response.
    """

    status: str = Field(
        description="API execution status."
    )

    model_version: str = Field(
        description="Production model version."
    )

    # --------------------------------------------------------------
    # Live weather
    # --------------------------------------------------------------

    weather: LiveWeatherResponse

    # --------------------------------------------------------------
    # Live traffic
    # --------------------------------------------------------------

    traffic: LiveTrafficResponse

    # --------------------------------------------------------------
    # ML predictions
    # --------------------------------------------------------------

    delivery_charge: float = Field(
        description="Predicted delivery charge in INR."
    )

    delivery_time_minutes: float = Field(
        description="Predicted delivery time in minutes."
    )

    rider_acceptance_probability: float = Field(
        description="Probability that the rider accepts the order."
    )

    rider_acceptance: int = Field(
        description="Predicted rider acceptance class: 0 or 1."
    )

# ======================================================================
# HEALTH RESPONSE
# ======================================================================

class HealthResponse(BaseModel):
    """
    API health-check response.
    """

    status: str

    model_version: str

    delivery_charge_model: str

    delivery_time_model: str

    rider_acceptance_model: str

    weather_provider: str = "available"

    traffic_provider: str = "available"


# ======================================================================
# ERROR RESPONSE
# ======================================================================

class ErrorResponse(BaseModel):
    """
    Standard API error response.
    """

    status: str

    error: str

    detail: Optional[str] = None