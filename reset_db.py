import sqlite3

# Database filename
DB_NAME = "nutriscan.db"


def reset_database():
    """
    Delete all food logs from the database.

    Useful for:
    - Testing
    - Demo resets
    - Judge evaluations
    """

    # Connect to SQLite database
    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    # Check that the table exists before deleting data
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'daily_logs'
    """)

    table_exists = cursor.fetchone()

    if table_exists:

        # Delete all food records
        cursor.execute("DELETE FROM daily_logs")

        # Reset auto-increment counter
        cursor.execute("""
            DELETE FROM sqlite_sequence
            WHERE name = 'daily_logs'
        """)

        # Save changes
        connection.commit()

        print("Database reset successfully.")
        print("All food logs have been deleted.")

    else:

        print("Database table does not exist.")

    # Close connection
    connection.close()


# Execute reset script
if __name__ == "__main__":
    reset_database()