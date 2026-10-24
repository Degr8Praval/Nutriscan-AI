"""
build_food_db.py - One-time converter from Hugging Face to indexed SQLite
Run once via: python3 build_food_db.py
"""

import sqlite3
import pandas as pd

print("1. Downloading & streaming MM-Food-100K from Hugging Face...")
# If needed, install: pip install fsspec huggingface_hub
url = "hf://datasets/Humanbased-AI/MM-Food-100K/MM-Food-100K.csv"
df = pd.read_csv(url)

print(f"Loaded {len(df)} rows. Columns found: {list(df.columns)}")

# Normalize column names to lowercase for consistency
df.columns = [c.strip().lower() for c in df.columns]

# Map columns flexibly based on MM-Food-100K schema
name_col = "title" if "title" in df.columns else "food_name"
ingr_col = "ingredients" if "ingredients" in df.columns else "recipe"
cal_col = "calories" if "calories" in df.columns else "energy_kcal"
pro_col = "protein" if "protein" in df.columns else "proteins"
carb_col = "carbohydrates" if "carbohydrates" in df.columns else "carbs"
fat_col = "fat" if "fat" in df.columns else "fats"

clean_df = pd.DataFrame({
    "food_name": df[name_col].astype(str),
    "ingredients": df[ingr_col].astype(str),
    "calories": pd.to_numeric(df[cal_col], errors="coerce").fillna(140.0),
    "protein": pd.to_numeric(df[pro_col], errors="coerce").fillna(5.0),
    "carbs": pd.to_numeric(df[carb_col], errors="coerce").fillna(20.0),
    "fat": pd.to_numeric(df[fat_col], errors="coerce").fillna(3.0)
})

print("2. Storing into indexed SQLite database (food_data.db)...")
conn = sqlite3.connect("food_data.db")
clean_df.to_sql("recipes", conn, if_exists="replace", index=False)

# Add B-Tree indexes for fast text lookups
conn.execute("CREATE INDEX IF NOT EXISTS idx_food_name ON recipes(food_name);")
conn.close()

print("Done! 'food_data.db' is ready with 100,000 indexed food items.")