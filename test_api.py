from food_api import get_food_data

# Test food search
food = get_food_data("oats")

if food:
    print("\nFood Found!")
    print("Name:", food["name"])
    print("Calories:", food["calories"])
    print("Protein:", food["protein"])
    print("Carbs:", food["carbs"])
    print("Fat:", food["fat"])
else:
    print("API request failed.")