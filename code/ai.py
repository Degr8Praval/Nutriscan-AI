"""Stable, lazy application-facing entry point for Gemma image analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def analyze_meal_image(image_path: str | Path) -> dict[str, Any]:
    """Load the vision stack only when a user actually analyzes an image."""
    try:
        from .gemma_vision import analyze_meal_image as analyze
    except ImportError as exc:
        if exc.name not in (None, "gemma_vision"):
            raise
        from gemma_vision import analyze_meal_image as analyze
    return analyze(image_path)


__all__ = ["analyze_meal_image"]
