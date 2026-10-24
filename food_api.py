import requests
import time


def get_food_data(food_name):
    """
    Search Open Food Facts for food products.

    Allow the user to select the correct product.

    Returns nutritional values per 100 grams.
    """

    url = "https://world.openfoodfacts.org/cgi/search.pl"

    params = {
        "search_terms": food_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 20
    }

    headers = {
        "User-Agent": "NutriScan/1.0 (contact: your-email@example.com)"
    }

    # Retry API requests up to 3 times
    for attempt in range(3):

        try:
            print(f"\nSearching for {food_name}...")

            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=20
            )

            if response.status_code in [429, 500, 502, 503, 504]:

                print("API temporarily unavailable. Retrying...")

                time.sleep(2 * (attempt + 1))
                continue

            response.raise_for_status()

            data = response.json()

            products = data.get("products", [])

            valid_products = []

            # Find products with complete nutrition information
            for product in products:

                nutrients = product.get("nutriments", {})

                calories = nutrients.get("energy-kcal_100g")
                protein = nutrients.get("proteins_100g")
                carbs = nutrients.get("carbohydrates_100g")
                fat = nutrients.get("fat_100g")

                if any(
                    value is None
                    for value in [calories, protein, carbs, fat]
                ):
                    continue

                valid_products.append({
                    "name": product.get("product_name") or food_name,
                    "calories": float(calories),
                    "protein": float(protein),
                    "carbs": float(carbs),
                    "fat": float(fat)
                })

            if not valid_products:

                print("No nutritional information found.")
                return None

            # Display products
            print("\nAvailable food products:\n")

            for index, product in enumerate(valid_products, start=1):

                print(
                    f"{index}. {product['name']} "
                    f"({product['calories']} kcal/100g)"
                )

            # Ask user to select the correct product
            while True:

                try:
                    choice = int(
                        input("\nSelect product number: ")
                    )

                    if 1 <= choice <= len(valid_products):

                        selected_food = valid_products[choice - 1]

                        print(
                            f"\nSelected: {selected_food['name']}"
                        )

                        return selected_food

                    print("Invalid selection.")

                except ValueError:

                    print("Please enter a valid number.")

        except requests.exceptions.RequestException as error:

            print("API Error:", error)

            time.sleep(2)

        except (ValueError, TypeError) as error:

            print("Invalid nutritional data:", error)
            return None

    print("Unable to retrieve food information.")

    return None