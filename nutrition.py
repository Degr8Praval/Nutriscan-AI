import sqlite3
from datetime import datetime

# Import the API function
from food_api import get_food_data


# SQLite database filename
DB_NAME = "nutriscan.db"


# -----------------------------------------
# HOUR 1: DATABASE SETUP
# -----------------------------------------

def initialize_database():
    """
    Create the SQLite database and daily_logs table.

    The table stores:
    - timestamp
    - food name
    - grams
    - calories
    - protein
    - carbs
    - fat
    """

    # Connect to SQLite database
    # SQLite automatically creates the database if it doesn't exist
    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    # Create daily_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT NOT NULL,

            food TEXT NOT NULL,

            grams REAL NOT NULL,

            calories REAL NOT NULL,

            protein REAL NOT NULL,

            carbs REAL NOT NULL,

            fat REAL NOT NULL

        )
    """)

    # Save database changes
    connection.commit()

    # Close database connection
    connection.close()

    print("Database initialized successfully.")


# -----------------------------------------
# HOUR 2: FOOD INTAKE LOGIC
# -----------------------------------------

def record_food_entry(name, grams):
    """
    Record food consumption.

    Steps:
    1. Search food using Open Food Facts.
    2. Retrieve nutrition per 100 grams.
    3. Scale nutrition based on consumed grams.
    4. Save the result in SQLite.
    """

    # Validate grams
    if grams <= 0:
        print("Grams must be greater than zero.")
        return

    # Fetch food nutrition information
    food_data = get_food_data(name)

    # Stop if food was not found
    if food_data is None:
        print("Unable to record food.")
        return

    # ---------------------------------
    # Calculate nutrition multiplier
    # ---------------------------------

    # API values are based on 100 grams
    multiplier = grams / 100

    # Scale calories and macronutrients
    calories = food_data["calories"] * multiplier

    protein = food_data["protein"] * multiplier

    carbs = food_data["carbs"] * multiplier

    fat = food_data["fat"] * multiplier

    # Get current timestamp
    timestamp = datetime.now().isoformat(timespec="seconds")

    # Connect to SQLite
    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    # Insert food entry into database
    cursor.execute("""
        INSERT INTO daily_logs (
            timestamp,
            food,
            grams,
            calories,
            protein,
            carbs,
            fat
        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp,
        food_data["name"],
        grams,
        calories,
        protein,
        carbs,
        fat
    ))

    # Save changes
    connection.commit()

    # Close connection
    connection.close()

    # Display confirmation
    print("\nFood recorded successfully!")

    print("Food:", food_data["name"])
    print("Grams:", grams)

    print(f"Calories: {calories:.2f} kcal")
    print(f"Protein: {protein:.2f} g")
    print(f"Carbs: {carbs:.2f} g")
    print(f"Fat: {fat:.2f} g")


# -----------------------------------------
# HOUR 3: DAILY TOTALS
# -----------------------------------------

def get_daily_totals():
    """
    Calculate total nutrition consumed today.

    Returns:
    - Total calories
    - Total protein
    - Total carbohydrates
    - Total fat
    """

    # Get today's date
    today = datetime.now().date().isoformat()

    # Connect to SQLite database
    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    # Calculate daily totals using SQL SUM()
    cursor.execute("""
        SELECT

            COALESCE(SUM(calories), 0),

            COALESCE(SUM(protein), 0),

            COALESCE(SUM(carbs), 0),

            COALESCE(SUM(fat), 0)

        FROM daily_logs

        WHERE timestamp >= ?
          AND timestamp < ?

    """, (
        today,
        today + "T\uffff"
    ))

    # Fetch result
    result = cursor.fetchone()

    # Close connection
    connection.close()

    # Store totals in dictionary
    totals = {
        "calories": round(result[0], 2),
        "protein": round(result[1], 2),
        "carbs": round(result[2], 2),
        "fat": round(result[3], 2)
    }

    return totals


# -----------------------------------------
# DISPLAY DAILY TOTALS
# -----------------------------------------

def display_daily_totals():
    """
    Print today's nutritional totals.
    """

    totals = get_daily_totals()

    print("\n========== DAILY NUTRITION ==========")

    print(f"Calories: {totals['calories']} kcal")

    print(f"Protein: {totals['protein']} g")

    print(f"Carbs: {totals['carbs']} g")

    print(f"Fat: {totals['fat']} g")

    print("=====================================")


# -----------------------------------------
# MAIN PROGRAM
# -----------------------------------------

def main():
    """
    Simple command-line interface.
    """

    # Initialize database before using it
    initialize_database()

    while True:

        print("\n========== NUTRISCAN ==========")

        print("1. Record Food")
        print("2. View Daily Totals")
        print("3. Exit")

        choice = input("\nEnter your choice: ")

        if choice == "1":

            # Ask user for food name
            food_name = input("Enter food name: ")

            try:
                # Ask user for consumed grams
                grams = float(input("Enter grams consumed: "))

                # Record food intake
                record_food_entry(food_name, grams)

            except ValueError:
                print("Invalid grams. Please enter a number.")

        elif choice == "2":

            # Display total nutrition for today
            display_daily_totals()

        elif choice == "3":

            print("Goodbye!")
            break

        else:

            print("Invalid choice. Try again.")


# Run program only when executed directly
if __name__ == "__main__":
    main()