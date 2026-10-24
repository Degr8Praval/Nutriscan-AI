# NutriScan

NutriScan is a local Streamlit prototype with a text-based dietary checker, an image-based meal checker, and an intake dashboard. The app runs locally and uses Ollama for image recognition and optional dietary reasoning.

## Run on Windows

Create the environment and install dependencies without activating PowerShell scripts:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Install Ollama and the AI models

The Python requirements install the Ollama client, but they do **not** install Ollama itself or download its AI models. Install the [Ollama app for Windows](https://ollama.com/download/windows), open it, then use PowerShell to download both models used by this app:

```powershell
ollama pull gemma4:e2b
ollama pull qwen2.5:1.5b
ollama list
```

- **`gemma4:e2b`** analyzes meal photos and estimates visible foods and portions. It must be a vision-capable model. [Ollama model page](https://ollama.com/library/gemma4:e2b)
- **`qwen2.5:1.5b`** is used by the dietary checker for its optional local language-model fallback. [Ollama model page](https://ollama.com/library/qwen2.5:1.5b)

Keep Ollama running while using NutriScan. On Windows, the Ollama app normally starts its local service at `http://127.0.0.1:11434`. If your service uses another address, set `OLLAMA_HOST` to that address. The photo analyzer defaults to `gemma4:e2b`; if you installed another vision-capable model instead, set `NUTRISCAN_MODEL` to its exact tag before launching:

```powershell
$env:NUTRISCAN_MODEL = "gemma4:e2b"
.\.venv\Scripts\python.exe -m streamlit run code/app.py
```

If Ollama is not running or the selected model has not been pulled, image analysis cannot start. The text checker can still use its local rules and fallback behavior.

## App tabs

- **Text food check**: enter a dish or ingredient and screen it against the category selected in the sidebar.
- **Check a meal photo**: upload an image; the local vision model identifies foods and estimated portions, then the app checks the detected names against the selected category. There are no food-name text fields in this tab.
- **Today's Intake Log**: view the session's saved entries and nutrition chart. The current dashboard log is held in Streamlit session state and resets when its session is cleared.

Diet checks use `code/diet_guard.py` and `code/diet_rules.json`. The vision flow is `code/vision_pipeline.py` → `code/ai.py` → `code/gemma_vision.py`. A dish-name check cannot identify hidden ingredients or cross-contamination; verify ingredients with the restaurant or package label.

## Nutrition data

The dashboard looks for a root-level `food_data.db` with a `recipes` table, as produced by `code/build_food.py` or `code/build_food_db.py`. Without that optional dataset, it uses nutrition references from `code/diet_rules.json` when available and otherwise displays fallback estimates.

`code/database.py` also provides a USDA Foundation Foods SQLite catalog at `data/nutriscan.db`, with the CLI in `code/nutrition.py` and reset helper in `code/reset_db.py`. It can import `FoodData_Central_foundation_food_json_2026-04-30.zip` placed one folder above the project. This USDA database helper is separate from the Streamlit dashboard's current `food_data.db` lookup.
