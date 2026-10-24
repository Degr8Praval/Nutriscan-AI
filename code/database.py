"""Local SQLite nutrition catalog and daily meal log for NutriScan.

The USDA Foundation Foods archive is imported once into SQLite.  All food
lookups and meal calculations after import are local and require no network.
Nutrition values are stored per 100 g and scaled deterministically when a
meal is logged.
"""

from __future__ import annotations

import json
import math
import sqlite3
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nutriscan.db"
DEFAULT_FDC_ARCHIVE = (
    PROJECT_ROOT.parent / "FoodData_Central_foundation_food_json_2026-04-30.zip"
)
FDC_SOURCE = "USDA FoodData Central Foundation Foods"


class FoodNotFoundError(LookupError):
    """Raised when a food cannot be matched safely to the local catalog."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS foods (
    fdc_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT,
    calories_per_100g REAL NOT NULL,
    protein_per_100g REAL NOT NULL,
    carbs_per_100g REAL NOT NULL,
    fat_per_100g REAL NOT NULL,
    source TEXT NOT NULL,
    publication_date TEXT
);

CREATE INDEX IF NOT EXISTS idx_foods_description ON foods(description);

CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    fdc_id INTEGER,
    food_name TEXT NOT NULL,
    grams REAL NOT NULL CHECK (grams > 0),
    calories REAL NOT NULL,
    protein REAL NOT NULL,
    carbs REAL NOT NULL,
    fat REAL NOT NULL,
    source TEXT NOT NULL,
    FOREIGN KEY (fdc_id) REFERENCES foods(fdc_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_logs_timestamp ON daily_logs(timestamp);
"""


def _connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _nutrients(food: dict[str, Any]) -> dict[str, float]:
    """Extract the four values NutriScan needs, all expressed per 100 g."""
    found: dict[str, float] = {}
    for item in food.get("foodNutrients", []):
        if not isinstance(item, dict):
            continue
        nutrient = item.get("nutrient") or {}
        name = nutrient.get("name")
        unit = str(nutrient.get("unitName", "")).lower()
        amount = item.get("amount")
        if amount is None:
            continue
        try:
            value = float(amount)
        except (TypeError, ValueError):
            continue
        if name == "Energy" and unit == "kcal":
            found["calories"] = value
        elif name == "Protein" and unit == "g":
            found["protein"] = value
        elif name == "Carbohydrate, by difference" and unit == "g":
            found["carbs"] = value
        elif name == "Total lipid (fat)" and unit == "g":
            found["fat"] = value
    return found


def _food_rows(json_data: dict[str, Any]) -> list[tuple[Any, ...]]:
    foods = json_data.get("FoundationFoods")
    if not isinstance(foods, list):
        raise ValueError("JSON does not contain a FoundationFoods list")

    rows: list[tuple[Any, ...]] = []
    required = {"calories", "protein", "carbs", "fat"}
    for food in foods:
        if not isinstance(food, dict):
            continue
        values = _nutrients(food)
        if not required.issubset(values):
            continue
        fdc_id = food.get("fdcId")
        description = food.get("description")
        if fdc_id is None or not description:
            continue
        category = food.get("foodCategory") or {}
        rows.append(
            (
                int(fdc_id),
                str(description),
                category.get("description"),
                values["calories"],
                values["protein"],
                values["carbs"],
                values["fat"],
                FDC_SOURCE,
                food.get("publicationDate"),
            )
        )
    return rows


def import_foundation_foods(
    archive_path: str | Path = DEFAULT_FDC_ARCHIVE,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Import the Foundation Foods JSON in the supplied USDA ZIP archive.

    Re-running is safe: records are upserted by FDC ID. Returns the number of
    usable foods imported. The archive is read directly; it is not extracted.
    """
    archive = Path(archive_path)
    if not archive.is_file():
        raise FileNotFoundError(f"USDA Foundation Foods archive not found: {archive}")
    with zipfile.ZipFile(archive) as zipped:
        json_names = [name for name in zipped.namelist() if name.lower().endswith(".json")]
        if len(json_names) != 1:
            raise ValueError(
                f"Expected one JSON file in USDA archive, found {len(json_names)}"
            )
        with zipped.open(json_names[0]) as stream:
            rows = _food_rows(json.load(stream))

    with _connect(db_path) as connection:
        connection.executemany(
            """INSERT INTO foods (
                   fdc_id, description, category, calories_per_100g,
                   protein_per_100g, carbs_per_100g, fat_per_100g,
                   source, publication_date
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(fdc_id) DO UPDATE SET
                   description=excluded.description,
                   category=excluded.category,
                   calories_per_100g=excluded.calories_per_100g,
                   protein_per_100g=excluded.protein_per_100g,
                   carbs_per_100g=excluded.carbs_per_100g,
                   fat_per_100g=excluded.fat_per_100g,
                   source=excluded.source,
                   publication_date=excluded.publication_date""",
            rows,
        )
    return len(rows)


def initialize_database(
    db_path: str | Path = DEFAULT_DB_PATH,
    archive_path: str | Path | None = None,
) -> int:
    """Create the schema and seed it from the archive if the catalog is empty.

    Returns the number of foods imported (zero if already seeded or if the
    optional archive is not present).
    """
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)
        existing = connection.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
    archive = Path(archive_path) if archive_path is not None else DEFAULT_FDC_ARCHIVE
    if existing == 0 and archive.is_file():
        return import_foundation_foods(archive, db_path)
    return 0


def search_foods(
    query: str, limit: int = 10, db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Return local catalog matches, preferring descriptions that start alike."""
    query = query.strip()
    if not query:
        return []
    limit = max(1, min(int(limit), 100))
    with _connect(db_path) as connection:
        rows = connection.execute(
            """SELECT * FROM foods
               WHERE description LIKE ? COLLATE NOCASE
               ORDER BY CASE WHEN description LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                        description COLLATE NOCASE
               LIMIT ?""",
            (f"%{query}%", f"{query}%", limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _resolve_food(
    name: str, connection: sqlite3.Connection, fdc_id: int | None = None
) -> sqlite3.Row:
    if fdc_id is not None:
        row = connection.execute("SELECT * FROM foods WHERE fdc_id = ?", (fdc_id,)).fetchone()
        if row is None:
            raise FoodNotFoundError(f"No local USDA food with FDC ID {fdc_id}")
        return row

    normalized = " ".join(name.casefold().split())
    rows = connection.execute("SELECT * FROM foods").fetchall()
    exact = [row for row in rows if " ".join(row["description"].casefold().split()) == normalized]
    if len(exact) == 1:
        return exact[0]

    # Accept a unique substring match only. Ambiguous or approximate matches
    # must be selected by the caller instead of silently logging the wrong food.
    matches = [row for row in rows if normalized in " ".join(row["description"].casefold().split())]
    if len(matches) == 1:
        return matches[0]
    candidates = ", ".join(f"{r['description']} (FDC {r['fdc_id']})" for r in matches[:5])
    if candidates:
        raise FoodNotFoundError(
            f"'{name}' is ambiguous; choose a local catalog match: {candidates}"
        )
    raise FoodNotFoundError(
        f"'{name}' is not in the local catalog. Search foods and choose an FDC ID."
    )


def record_food_entry(
    name: str,
    grams: float,
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    fdc_id: int | None = None,
) -> dict[str, Any]:
    """Scale catalog macros by grams, then append a timestamped meal log row."""
    try:
        grams = float(grams)
    except (TypeError, ValueError) as exc:
        raise ValueError("grams must be a positive number") from exc
    if not math.isfinite(grams) or grams <= 0:
        raise ValueError("grams must be a positive finite number")

    with _connect(db_path) as connection:
        food = _resolve_food(name, connection, fdc_id)
        factor = grams / 100.0
        entry = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "fdc_id": food["fdc_id"],
            "food_name": food["description"],
            "grams": grams,
            "calories": food["calories_per_100g"] * factor,
            "protein": food["protein_per_100g"] * factor,
            "carbs": food["carbs_per_100g"] * factor,
            "fat": food["fat_per_100g"] * factor,
            "source": food["source"],
        }
        cursor = connection.execute(
            """INSERT INTO daily_logs
               (timestamp, fdc_id, food_name, grams, calories, protein, carbs, fat, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(entry[key] for key in (
                "timestamp", "fdc_id", "food_name", "grams", "calories",
                "protein", "carbs", "fat", "source"
            )),
        )
        entry["id"] = cursor.lastrowid
    return entry


def record_food_entries(
    entries: list[dict[str, Any]], db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Save all reviewed items in one transaction, or save none of the meal."""
    if not entries:
        raise ValueError("A meal must contain at least one food entry")

    prepared: list[tuple[int, float]] = []
    for item in entries:
        try:
            fdc_id = int(item["fdc_id"])
            grams = float(item["grams"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Each meal entry needs a USDA food ID and gram weight") from exc
        if fdc_id <= 0 or not math.isfinite(grams) or grams <= 0:
            raise ValueError("Food IDs and gram weights must be positive finite numbers")
        prepared.append((fdc_id, grams))

    connection = _connect(db_path)
    try:
        saved: list[dict[str, Any]] = []
        with connection:
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            for fdc_id, grams in prepared:
                food = _resolve_food("", connection, fdc_id)
                scale = grams / 100
                entry = {
                    "timestamp": timestamp,
                    "fdc_id": food["fdc_id"],
                    "food_name": food["description"],
                    "grams": grams,
                    "calories": food["calories_per_100g"] * scale,
                    "protein": food["protein_per_100g"] * scale,
                    "carbs": food["carbs_per_100g"] * scale,
                    "fat": food["fat_per_100g"] * scale,
                    "source": food["source"],
                }
                cursor = connection.execute(
                    """INSERT INTO daily_logs
                       (timestamp, fdc_id, food_name, grams, calories, protein, carbs, fat, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    tuple(entry[key] for key in (
                        "timestamp", "fdc_id", "food_name", "grams", "calories",
                        "protein", "carbs", "fat", "source"
                    )),
                )
                entry["id"] = cursor.lastrowid
                saved.append(entry)
        return saved
    finally:
        connection.close()


def get_daily_totals(
    day: date | str | None = None, db_path: str | Path = DEFAULT_DB_PATH
) -> dict[str, Any]:
    """Aggregate entries whose saved local timestamp falls on ``day``."""
    day_text = (day or date.today()).isoformat() if isinstance(day, date) else (day or date.today().isoformat())
    with _connect(db_path) as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS entries,
                      COALESCE(SUM(calories), 0) AS calories,
                      COALESCE(SUM(protein), 0) AS protein,
                      COALESCE(SUM(carbs), 0) AS carbs,
                      COALESCE(SUM(fat), 0) AS fat
               FROM daily_logs WHERE substr(timestamp, 1, 10) = ?""",
            (day_text,),
        ).fetchone()
    return {"date": day_text, **dict(row)}


def get_daily_entries(
    day: date | str | None = None, db_path: str | Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Return today's saved food rows in timestamp order for the UI."""
    day_text = (day or date.today()).isoformat() if isinstance(day, date) else (day or date.today().isoformat())
    with _connect(db_path) as connection:
        rows = connection.execute(
            """SELECT id, timestamp, fdc_id, food_name, grams, calories,
                      protein, carbs, fat, source
               FROM daily_logs WHERE substr(timestamp, 1, 10) = ?
               ORDER BY timestamp, id""",
            (day_text,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_food_count(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Return the number of locally imported foods."""
    with _connect(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM foods").fetchone()[0])


if __name__ == "__main__":
    imported = initialize_database()
    print(f"NutriScan database ready: {DEFAULT_DB_PATH}")
    print(f"Imported {imported} USDA Foundation Foods entries; catalog has {get_food_count()} foods.")
