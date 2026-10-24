"""Simple command-line front end to NutriScan's shared USDA/SQLite database."""

from database import (
    DEFAULT_DB_PATH,
    get_daily_totals,
    initialize_database,
    record_food_entry,
    search_foods,
)


def main() -> None:
    initialize_database()
    while True:
        print("\nNutriScan nutrition log")
        print("1. Search and log food")
        print("2. Show today's totals")
        print("3. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            query = input("Food search: ").strip()
            matches = search_foods(query, limit=8)
            if not matches:
                print("No local USDA match found. Try a simpler search term.")
                continue
            for index, food in enumerate(matches, start=1):
                print(f"{index}. {food['description']} — {food['calories_per_100g']:.0f} kcal/100 g")
            try:
                selected = int(input("Select a match: ")) - 1
                food = matches[selected]
                grams = float(input("Grams eaten: "))
                entry = record_food_entry(
                    food["description"], grams, fdc_id=int(food["fdc_id"])
                )
            except (ValueError, IndexError):
                print("Choose a listed number and enter a positive gram amount.")
                continue
            print(
                f"Saved {entry['food_name']} ({entry['grams']:.0f} g): "
                f"{entry['calories']:.0f} kcal, protein {entry['protein']:.1f} g, "
                f"carbs {entry['carbs']:.1f} g, fat {entry['fat']:.1f} g."
            )
        elif choice == "2":
            totals = get_daily_totals()
            print(
                f"Today: {totals['calories']:.0f} kcal · protein {totals['protein']:.1f} g · "
                f"carbs {totals['carbs']:.1f} g · fat {totals['fat']:.1f} g"
            )
        elif choice == "3":
            return
        else:
            print("Enter 1, 2, or 3.")


if __name__ == "__main__":
    print(f"Using database: {DEFAULT_DB_PATH}")
    main()
