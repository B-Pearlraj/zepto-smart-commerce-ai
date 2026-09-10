
"""
Production inference engine for the
Zepto Smart Commerce AI Platform.

Model Version:
    HGB-v1

Models:
    1. Delivery Charge
    2. Delivery Time
    3. Rider Acceptance
"""

from pathlib import Path
import json
import math

import joblib
import numpy as np
import pandas as pd


# ======================================================================
# PATHS
# ======================================================================

APP_DIR = Path(__file__).resolve().parent

MODEL_DIR = APP_DIR / "models"
CONFIG_DIR = APP_DIR / "config"


# ======================================================================
# MODEL PACKAGE PATHS
# ======================================================================

CHARGE_PACKAGE = (
    MODEL_DIR / "delivery_charge_complete_package.joblib"
)

TIME_PACKAGE = (
    MODEL_DIR / "delivery_time_complete_package.joblib"
)

ACCEPTANCE_PACKAGE = (
    MODEL_DIR / "rider_acceptance_complete_package.joblib"
)


# ======================================================================
# FEATURE CONFIGURATION
# ======================================================================

FEATURE_CONFIGURATION_FILE = (
    CONFIG_DIR / "production_feature_configuration.json"
)


# ======================================================================
# VALIDATE FILES
# ======================================================================

for package_path in [
    CHARGE_PACKAGE,
    TIME_PACKAGE,
    ACCEPTANCE_PACKAGE,
]:

    if not package_path.exists():
        raise FileNotFoundError(
            f"Production model package not found: {package_path}"
        )


if not FEATURE_CONFIGURATION_FILE.exists():
    raise FileNotFoundError(
        "Production feature configuration not found."
    )


# ======================================================================
# LOAD PRODUCTION PACKAGES
# ======================================================================

charge_package = joblib.load(CHARGE_PACKAGE)
time_package = joblib.load(TIME_PACKAGE)
acceptance_package = joblib.load(ACCEPTANCE_PACKAGE)


# ======================================================================
# VALIDATE PACKAGE STRUCTURE
# ======================================================================

def validate_package(package, package_name):
    """
    Validate production model package structure.
    """

    if not isinstance(package, dict):
        raise TypeError(
            f"{package_name} package must be a dictionary."
        )

    required_keys = [
        "model",
        "preprocessor",
    ]

    for key in required_keys:

        if key not in package:
            raise KeyError(
                f"{package_name} package missing key: {key}"
            )

        if package[key] is None:
            raise ValueError(
                f"{package_name} package contains None for: {key}"
            )


validate_package(
    charge_package,
    "Delivery Charge"
)

validate_package(
    time_package,
    "Delivery Time"
)

validate_package(
    acceptance_package,
    "Rider Acceptance"
)


# ======================================================================
# EXTRACT MODELS AND PREPROCESSORS
# ======================================================================

charge_model = charge_package["model"]
charge_preprocessor = charge_package["preprocessor"]

time_model = time_package["model"]
time_preprocessor = time_package["preprocessor"]

acceptance_model = acceptance_package["model"]
acceptance_preprocessor = acceptance_package["preprocessor"]


# ======================================================================
# LOAD FEATURE CONFIGURATION
# ======================================================================

with open(
    FEATURE_CONFIGURATION_FILE,
    "r",
    encoding="utf-8"
) as f:

    feature_configuration = json.load(f)


# ======================================================================
# FEATURE EXTRACTION
# ======================================================================

def extract_feature_list(configuration, model_name):
    """
    Extract a model feature list from the production configuration.
    """

    if model_name in configuration:

        model_config = configuration[model_name]

        if isinstance(model_config, dict):

            for key in [
                "features",
                "feature_names",
                "selected_features",
                "model_features",
            ]:

                if key in model_config:

                    value = model_config[key]

                    if isinstance(value, list):
                        return list(value)

        if isinstance(model_config, list):
            return list(model_config)

    # Case-insensitive lookup
    for key, value in configuration.items():

        if str(key).lower() == model_name.lower():

            if isinstance(value, dict):

                for feature_key in [
                    "features",
                    "feature_names",
                    "selected_features",
                    "model_features",
                ]:

                    if feature_key in value:

                        feature_value = value[
                            feature_key
                        ]

                        if isinstance(
                            feature_value,
                            list
                        ):
                            return list(feature_value)

            if isinstance(value, list):
                return list(value)

    return None


# ----------------------------------------------------------------------
# Extract model feature lists
# ----------------------------------------------------------------------

charge_features = extract_feature_list(
    feature_configuration,
    "delivery_charge"
)

time_features = extract_feature_list(
    feature_configuration,
    "delivery_time"
)

acceptance_features = extract_feature_list(
    feature_configuration,
    "rider_acceptance"
)


# ----------------------------------------------------------------------
# Fallback names
# ----------------------------------------------------------------------

if charge_features is None:

    charge_features = extract_feature_list(
        feature_configuration,
        "charge"
    )


if time_features is None:

    time_features = extract_feature_list(
        feature_configuration,
        "time"
    )


if acceptance_features is None:

    acceptance_features = extract_feature_list(
        feature_configuration,
        "acceptance"
    )


# ======================================================================
# VALIDATE FEATURE LISTS
# ======================================================================

if charge_features is None:
    raise ValueError(
        "Delivery Charge feature list could not be extracted."
    )

if time_features is None:
    raise ValueError(
        "Delivery Time feature list could not be extracted."
    )

if acceptance_features is None:
    raise ValueError(
        "Rider Acceptance feature list could not be extracted."
    )


charge_features = list(charge_features)
time_features = list(time_features)
acceptance_features = list(acceptance_features)


# ======================================================================
# EXPECTED PRODUCTION FEATURE COUNTS
# ======================================================================

if len(charge_features) != 36:

    raise ValueError(
        f"Expected 36 charge features, "
        f"found {len(charge_features)}."
    )


if len(time_features) != 38:

    raise ValueError(
        f"Expected 38 time features, "
        f"found {len(time_features)}."
    )


if len(acceptance_features) != 39:

    raise ValueError(
        f"Expected 39 acceptance features, "
        f"found {len(acceptance_features)}."
    )


# ======================================================================
# INPUT PREPARATION
# ======================================================================

def prepare_for_model(X):
    """
    Prepare input DataFrame for the saved sklearn preprocessor.

    Categorical columns are converted from pandas Categorical
    to object so unseen API values can be handled safely.
    """

    X = X.copy()

    if not isinstance(X, pd.DataFrame):

        X = pd.DataFrame(X)

    for column in X.columns:

        if isinstance(
            X[column].dtype,
            pd.CategoricalDtype
        ):

            X[column] = X[column].astype(object)

    return X


# ======================================================================
# PRODUCTION PREDICTION FUNCTION
# ======================================================================

def production_predict_order(order_data):
    """
    Generate all three HGB-v1 production predictions.

    Parameters
    ----------
    order_data:
        Dictionary or one-row pandas DataFrame.

    Returns
    -------
    dict
        Delivery charge,
        delivery time,
        acceptance probability,
        acceptance classification.
    """

    # ------------------------------------------------------------------
    # Convert input
    # ------------------------------------------------------------------

    if isinstance(order_data, dict):

        X_order = pd.DataFrame(
            [order_data]
        )

    elif isinstance(order_data, pd.DataFrame):

        X_order = order_data.copy()

    else:

        raise TypeError(
            "order_data must be a dictionary "
            "or pandas DataFrame."
        )


    # ------------------------------------------------------------------
    # Validate input
    # ------------------------------------------------------------------

    if X_order.empty:

        raise ValueError(
            "order_data cannot be empty."
        )


    if len(X_order) != 1:

        raise ValueError(
            "production_predict_order accepts "
            "exactly one order."
        )


    # ------------------------------------------------------------------
    # Required feature validation
    # ------------------------------------------------------------------

    required_features = sorted(
        set(
            charge_features
            + time_features
            + acceptance_features
        )
    )

    missing_features = [
        feature
        for feature in required_features
        if feature not in X_order.columns
    ]

    if missing_features:

        raise ValueError(
            "Missing required production features: "
            + ", ".join(missing_features)
        )


    # ==================================================================
    # DELIVERY CHARGE
    # ==================================================================

    X_charge = X_order[
        charge_features
    ].copy()

    X_charge = prepare_for_model(
        X_charge
    )

    X_charge_processed = (
        charge_preprocessor.transform(
            X_charge
        )
    )

    charge_prediction = float(
        charge_model.predict(
            X_charge_processed
        )[0]
    )


    # ==================================================================
    # DELIVERY TIME
    # ==================================================================

    X_time = X_order[
        time_features
    ].copy()

    X_time = prepare_for_model(
        X_time
    )

    X_time_processed = (
        time_preprocessor.transform(
            X_time
        )
    )

    time_prediction = float(
        time_model.predict(
            X_time_processed
        )[0]
    )


    # ==================================================================
    # RIDER ACCEPTANCE
    # ==================================================================

    X_acceptance = X_order[
        acceptance_features
    ].copy()

    X_acceptance = prepare_for_model(
        X_acceptance
    )

    X_acceptance_processed = (
        acceptance_preprocessor.transform(
            X_acceptance
        )
    )

    acceptance_probability = float(
        acceptance_model.predict_proba(
            X_acceptance_processed
        )[0, 1]
    )

    acceptance_prediction = int(
        acceptance_probability >= 0.5
    )


    # ==================================================================
    # OUTPUT VALIDATION
    # ==================================================================

    values = [
        charge_prediction,
        time_prediction,
        acceptance_probability,
    ]

    if not all(
        math.isfinite(value)
        for value in values
    ):

        raise ValueError(
            "Production prediction contains "
            "a non-finite value."
        )


    if charge_prediction <= 0:

        raise ValueError(
            "Delivery charge prediction must be positive."
        )


    if time_prediction <= 0:

        raise ValueError(
            "Delivery time prediction must be positive."
        )


    if not (
        0 <= acceptance_probability <= 1
    ):

        raise ValueError(
            "Acceptance probability must be "
            "between 0 and 1."
        )


    if acceptance_prediction not in (0, 1):

        raise ValueError(
            "Acceptance prediction must be 0 or 1."
        )


    # ==================================================================
    # RETURN
    # ==================================================================

    return {
        "delivery_charge": charge_prediction,
        "delivery_time_minutes": time_prediction,
        "rider_acceptance_probability": (
            acceptance_probability
        ),
        "rider_acceptance": acceptance_prediction,
    }
