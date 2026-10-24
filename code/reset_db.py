"""Clear daily intake rows without deleting the local USDA catalog."""

from database import DEFAULT_DB_PATH, _connect, initialize_database


def reset_database(db_path=DEFAULT_DB_PATH) -> int:
    initialize_database(db_path=db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM daily_logs")
        deleted = cursor.rowcount
        connection.execute("DELETE FROM sqlite_sequence WHERE name = 'daily_logs'")
    return max(0, deleted)


if __name__ == "__main__":
    removed = reset_database()
    print(f"Cleared {removed} daily log entries from {DEFAULT_DB_PATH}.")
