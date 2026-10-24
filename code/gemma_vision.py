"""Local Gemma image analysis for meal photo suggestions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class FoodEstimate(BaseModel):
    name: str = Field(description="Short recognizable food name")
    grams: float = Field(gt=0, description="Estimated edible portion weight in grams")


class MealEstimate(BaseModel):
    foods: list[FoodEstimate]


def analyze_meal_image(image_path: str | Path) -> dict[str, Any]:
    """Ask local Ollama Gemma to identify visible foods and estimate grams."""
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama's Python package is missing. Install requirements.txt.") from exc

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError("Uploaded meal image could not be read.")

    model = os.environ.get("NUTRISCAN_MODEL", "gemma4:e2b")
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    prompt = (
        "Inspect this meal photo. Return only foods that are visibly present, each with a short "
        "food name and a rough estimate of edible portion weight in grams. Do not infer hidden "
        "ingredients, dietary labels, or nutrition values. If uncertain, provide your best "
        "estimate; the user will review and correct every result. Return an empty foods list "
        "if no food is visible."
    )
    try:
        client = ollama.Client(host=host)
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt, "images": [str(path)]}],
            format=MealEstimate.model_json_schema(),
            options={"temperature": 0},
        )
        parsed = MealEstimate.model_validate_json(response.message.content)
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if any(marker in lowered for marker in ("connect", "refused", "connectionerror", "connection error", "timed out", "timeout")):
            raise RuntimeError(
                f"Cannot reach the Ollama service at {host}. Open the Ollama app (or run `ollama serve`), "
                f"then confirm a vision-capable model is installed with `ollama list`. "
                f"This app is configured for `{model}`; install it with `ollama pull {model}` or set "
                "NUTRISCAN_MODEL to the exact installed vision-model tag."
            ) from exc
        if "not found" in lowered and model.lower() in lowered:
            raise RuntimeError(
                f"Ollama is running, but model `{model}` is not installed. Run `ollama pull {model}` "
                "or set NUTRISCAN_MODEL to the exact installed vision-model tag."
            ) from exc
        raise RuntimeError(f"Gemma image analysis failed: {message}") from exc
    return parsed.model_dump()
