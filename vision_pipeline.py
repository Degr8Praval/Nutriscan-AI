import ollama
import json
import re
import time
from pydantic import ValidationError
import pandas as pd
dt = pd.read_csv(df = pd.read_csv("hf://datasets/Humanbased-AI/MM-Food-100K/MM-Food-100K.csv"))

class FoodItem(BaseModel):
    def __init__(self, name, estimated_grams, confidence=0.8):
        self.name = name.strip().lower()
        grams = float(estimated_grams)
        if grams < 0:
            grams = 0  # can't have negative weight
        self.estimated_grams = grams

        # Confidence score, defaults to 0.8 if not provided.
        self.confidence = max(0.0, min(1.0, confidence))

    def to_dict(self):
        return {
            "name": self.name,
            "estimated_grams": self.estimated_grams,
            "confidence": self.confidence
        }

    def __repr__(self):
        """
        Controls how the object looks when you print it.
        """
        return f"FoodItem(name='{self.name}', grams={self.estimated_grams})"\
class plateExtraction():
    def __init__(self, items, success = True, error_msg = None): 
        self.items = items 
        self.success = success # did the vision extraction work? 
        self.error_msg = error_msg # if success is false
    def to_dict(items, success, error_msg): 
        ''' 
        Converts everything to a dictionary format.
        '''
         return {
            "success": self.success,
            "items": [item.to_dict() for item in self.items],
            "error_message": self.error_message
         }
    def __repr__(self):
        return f"PlateExtraction(success={self.success}, items={len(self.items)})"
# prompt 
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
    """call to Ollama, returns the model's text response."""
    response = ollama.chat(model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT,
                "images": [image_path],
            }
        ],
        options={
            "temperature": 0.1,    # low temp means more less creative hallucination
            "num_predict": 300,    # prevents rambling
        },
    )
    return response["message"]["content"]

def extract_plate_items(image_path: str, retries: int = 2):
    """
    Takes an image path, returns validated PlateExtraction.
    """
    last_error = None

    for attempt in range(retries + 1):
        try:
            raw_output = call_vision_model(processed_path)
            json_str = extract_json_block(raw_output)
            data = json.loads(json_str)

            result = PlateExtraction(
                items = [FoodItem(**item) for item in data.get("items", [])],
                raw_model_output = raw_output,
                success = True,
            )
            return result

        except (json.JSONDecodeError, ValidationError, KeyError) as err:
            last_error = str(err)
            time.sleep(0.5)  # brief pause before retrying
            continue
