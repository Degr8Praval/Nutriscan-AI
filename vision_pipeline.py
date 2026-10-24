import ollama
import json
import re
import time

class FoodItem:
    """
    Represents one food item found in a photo.
    """

    def __init__(self, name, estimated_grams, confidence=0.8):
        self.name = name.strip().lower()

        grams = float(estimated_grams)
        if grams < 0:
            grams = 0  # can't have negative weight
        if grams > 1000:
            grams = 1000  # cap unrealistic portion sizes

        self.estimated_grams = grams
        self.confidence = max(0.0, min(1.0, confidence))

    def to_dict(self):
        return {
            "name": self.name,
            "estimated_grams": self.estimated_grams,
            "confidence": self.confidence
        }

    def __repr__(self):
        return f"FoodItem(name='{self.name}', grams={self.estimated_grams})"
        # ^ removed the trailing backslash that was causing the SyntaxError

class PlateExtraction:
    """
    Represents the full result of analyzing one photo.
    """

    def __init__(self, items=None, success=True, error_message=None, raw_model_output=None):
        self.items = items or []
        self.success = success
        self.error_message = error_message       # renamed from error_msg for consistency
        self.raw_model_output = raw_model_output  # added so extract_plate_items() can pass it in

    def to_dict(self):
        return {
            "success": self.success,
            "items": [item.to_dict() for item in self.items],
            "error_message": self.error_message
        }

    def __repr__(self):
        return f"PlateExtraction(success={self.success}, items={len(self.items)})"


# ---------- PROMPT ----------

EXTRACTION_PROMPT = """You are a food identification system. Look at the image and identify each distinct food item visible on the plate.

Respond ONLY with valid JSON in this exact format, with no markdown, no explanation, no code fences:

{"items": [{"name": "grilled chicken breast", "estimated_grams": 150}, {"name": "white rice", "estimated_grams": 200}]}

Rules:
- List each visible food item separately (do not combine into one entry)
- Estimate portion weight in grams based on visual size relative to a standard dinner plate (27cm)
- Use common, simple food names (e.g. "rice" not "steamed basmati rice with garnish")
- If you cannot identify any food, return {"items": []}
- Output ONLY the JSON object, nothing else
"""


# ask AI baba

def call_vision_model(image_path: str, model: str = "moondream:v2"):
    """Call to Ollama, returns the model's text response."""
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT,
                "images": [image_path],
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 300,
        },
    )
    return response["message"]["content"]


# clean up outpt for JSON

def extract_json_block(text):
    """
    Extracts just the {...} JSON object from the model's raw text output,
    stripping away any markdown or commentary around it.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


# main func

def extract_plate_items(image_path: str, retries: int = 2):
    """
    Takes an image path, returns a validated PlateExtraction object.
    """
    last_error = None

    for attempt in range(retries + 1):
        try:
            raw_output = call_vision_model(image_path)
            json_str = extract_json_block(raw_output)
            data = json.loads(json_str)

            result = PlateExtraction(
                items=[FoodItem(**item) for item in data.get("items", [])],
                raw_model_output=raw_output,
                success=True,
            )
            return result

        except (json.JSONDecodeError, ValidationError, KeyError) as err:
            last_error = str(err)
            time.sleep(0.5)
            continue

    # All retries failed
    return PlateExtraction(
        items=[],
        success=False,
        error_message=f"Failed to parse vision output after {retries + 1} attempts: {last_error}",
        raw_model_output=last_error
    )