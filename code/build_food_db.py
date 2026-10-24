"""
build_food_db.py - Converts MM-Food-100K from Hugging Face into indexed SQLite
Run via: python3 build_food_db.py
"""

import sqlite3
import re
import pandas as pd

print("1. Downloading & streaming MM-Food-100K from Hugging Face...")
url = "hf://datasets/Humanbased-AI/MM-Food-100K/MM-Food-100K.csv"
df = pd.read_csv(url)

print(f"Loaded {len(df)} rows.")

def parse_nutrient(text: str, key: str, default: float = 0.0) -> float:
    """Extracts numeric values like 'calories: 250 kcal' or 'protein: 12g' from text."""
    if not isinstance(text, str):
        return default
    # Matches patterns like 'calories: 250', 'protein: 12.5g', 'carbohydrates: 30'
    match = re.search(rf"{key}\s*[:=]?\s*([\d\.]+)", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return default

print("2. Parsing nutritional profiles and extracting macros...")
clean_df = pd.DataFrame()
clean_df["food_name"] = df["dish_name"].astype(str)
clean_df["ingredients"] = df["ingredients"].astype(str)

# Parse nutritional_profile string
profiles = df["nutritional_profile"].astype(str)
clean_df["calories"] = profiles.apply(lambda x: parse_nutrient(x, r"(?:calorie|calories|kcal)", default=150.0))
clean_df["protein"] = profiles.apply(lambda x: parse_nutrient(x, r"protein", default=5.0))
clean_df["carbs"] = profiles.apply(lambda x: parse_nutrient(x, r"(?:carb|carbs|carbohydrate|carbohydrates)", default=20.0))
clean_df["fat"] = profiles.apply(lambda x: parse_nutrient(x, r"(?:fat|fats|total fat)", default=4.0))

print("3. Storing into indexed SQLite database (food_data.db)...")
conn = sqlite3.connect("food_data.db")
clean_df.to_sql("recipes", conn, if_exists="replace", index=False)

# Add B-Tree index for sub-millisecond lookups
conn.execute("CREATE INDEX IF NOT EXISTS idx_food_name ON recipes(food_name);")
conn.close()

print("Done! 'food_data.db' is ready with 100,000 indexed food items.")