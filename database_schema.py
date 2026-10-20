from create_orders_table import initialize_database
from database_repository import ensure_orders_table


def create_all_tables():
    print("=" * 70)
    print("CREATING POSTGRESQL TABLES")
    print("=" * 70)

    ensure_orders_table()
    print("orders table: CREATED / ALREADY EXISTS")

    initialize_database()
    print("prediction_audit table + indexes: CREATED / ALREADY EXISTS")

    print("\nSchema setup: PASSED")


if __name__ == "__main__":
    create_all_tables()
