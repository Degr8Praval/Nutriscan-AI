"""Compatibility adapter for Gemma meal-image analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # Package import, e.g. ``import code.vision_pipeline``.
    from .ai import analyze_meal_image
except ImportError:  # Streamlit executes app.py with ``code`` on sys.path.
    from ai import analyze_meal_image


@dataclass
class FoodItem:
    name: str
    estimated_grams: float
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "estimated_grams": self.estimated_grams,
            "confidence": self.confidence,
        }


@dataclass
class PlateExtraction:
    items: list[FoodItem] = field(default_factory=list)
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "items": [item.to_dict() for item in self.items],
            "error_message": self.error_message,
        }


def extract_plate_items(image_path: str) -> PlateExtraction:
    """Analyze a meal image with the configured local Ollama model."""
    try:
        result = analyze_meal_image(image_path)
        items = [
            FoodItem(name=item["name"], estimated_grams=float(item["grams"]))
            for item in result.get("foods", [])
        ]
        return PlateExtraction(items=items)
    except Exception as exc:
        return PlateExtraction(success=False, error_message=str(exc))


__all__ = ["FoodItem", "PlateExtraction", "extract_plate_items"]
