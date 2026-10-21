"""
Create and verify the PostgreSQL schema.

The table definitions now live in database_schema.py (one place for
both `orders` and `prediction_audit`). This script just runs that
setup and checks the result:

    python create_orders_table.py
"""

from database_schema import (
    create_all_tables,
    get_table_columns,
    get_table_indexes,
)


REQUIRED_PREDICTION_AUDIT_COLUMNS = [
    "id",
    "request_timestamp",
    "model_version",
    "delivery_charge",
    "delivery_time_minutes",
    "rider_acceptance_probability",
    "rider_acceptance",
    "weather_source",
    "traffic_source",
    "created_at",
]

REQUIRED_PREDICTION_AUDIT_INDEXES = [
    "idx_prediction_audit_request_timestamp",
    "idx_prediction_audit_model_version",
    "idx_prediction_audit_created_at",
]

REQUIRED_ORDERS_COLUMNS = [
    "order_id",
    "customer_name",
    "product_name",
    "order_status",
    "city",
    "distance_km",
    "order_amount",
    "festival_day_flag",
    "created_at",
    "updated_at",
]

REQUIRED_ORDERS_INDEXES = [
    "idx_orders_store_id",
    "idx_orders_city",
    "idx_orders_created_at",
]


def check(table, required_columns, required_indexes):

    columns = get_table_columns(table)
    indexes = get_table_indexes(table)

    print(f"\nTable: {table}")
    print("\nColumns:")

    for column in required_columns:
        assert column in columns, f"{table}: missing column {column}"
        print(f"  ✓ {column}")

    print("\nIndexes:")

    for index in required_indexes:
        assert index in indexes, f"{table}: missing index {index}"
        print(f"  ✓ {index}")


if __name__ == "__main__":

    print("=" * 70)
    print("POSTGRESQL SCHEMA INITIALIZATION")
    print("=" * 70)

    create_all_tables()

    check(
        "prediction_audit",
        REQUIRED_PREDICTION_AUDIT_COLUMNS,
        REQUIRED_PREDICTION_AUDIT_INDEXES,
    )

    check(
        "orders",
        REQUIRED_ORDERS_COLUMNS,
        REQUIRED_ORDERS_INDEXES,
    )

    print("\n" + "=" * 70)
    print("SCHEMA: PASSED")
    print("=" * 70)
