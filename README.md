# Zepto Smart Commerce AI API

Production model version: HGB-v1

## Models

1. Delivery Charge Prediction
2. Delivery Time Prediction
3. Rider Acceptance Prediction

## Model Family

HistGradientBoosting

## API Version

1.0.0

## Production Artifacts

The `models/` directory contains the validated production model packages.

The `config/` directory contains the production feature configuration,
model metadata, and API configuration.

## Validation

The HGB-v1 model packages were restored and validated before API assembly.

No model retraining is performed by the API.

## Endpoints

The FastAPI service will expose:

- `/`
- `/health`
- `/model-info`
- `/predict`
