"""
app.py - NutriScan & DietGuard Interactive Web Dashboard
Hacktoberfest 2026 - Edge Dietary Auditor
"""

import os
import json
import sqlite3
import datetime
import hashlib
import sys
import tempfile
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from PIL import Image

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from vision_pipeline import extract_plate_items

# 1. Page Config MUST be the very first Streamlit call
st.set_page_config(
    page_title="NutriScan AI - Edge Dietary Auditor",
    page_icon="🥗",
    layout="wide"
)

# ------------------------------------------------------------------------------
# 2. LOCAL DATA & ENGINE INITIALIZATION
# ------------------------------------------------------------------------------

DB_PATH = str(PROJECT_ROOT / "food_data.db")
RULES_PATH = str(CODE_DIR / "diet_rules.json")

@st.cache_resource
def get_diet_guard():
    """Initializes DietGuard lazily so the UI never blocks on boot."""
    try:
        from diet_guard import DietGuard
        return DietGuard(config_path=RULES_PATH, model="qwen2.5:1.5b")
    except Exception as e:
        st.sidebar.error(f"Engine Warning: {e}")
        return None

def query_food_nutrition(food_name: str) -> dict:
    """Checks SQLite DB first; falls back to diet_rules.json, then safe default."""
    clean = food_name.lower().strip()

    # 1. Check SQLite if built
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT food_name, calories, protein, carbs, fat, ingredients 
                FROM recipes 
                WHERE LOWER(food_name) LIKE ? 
                LIMIT 1
            """, (f"%{clean}%",))
            row = cur.fetchone()
            conn.close()
            if row:
                return {
                    "calories": float(row[1] or 140.0),
                    "protein": float(row[2] or 5.0),
                    "carbs": float(row[3] or 20.0),
                    "fat": float(row[4] or 3.0),
                    "source": "food_data.db"
                }
        except Exception:
            pass

    # 2. Check diet_rules.json
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                rules = json.load(f)
                ref = rules.get("nutrition_reference", {})
                for k, v in ref.items():
                    if k in clean or clean in k:
                        return {**v, "source": "diet_rules.json"}
        except Exception:
            pass

    # 3. Default fallback
    return {
        "calories": 140.0,
        "protein": 5.0,
        "carbs": 22.0,
        "fat": 3.0,
        "source": "fallback"
    }

# Initialize session state logs
if "daily_logs" not in st.session_state:
    st.session_state.daily_logs = [
        {"name": "Steamed Basmati Rice", "grams": 150, "calories": 181.5, "protein": 5.2, "carbs": 37.8, "fat": 0.6, "safe": True},
        {"name": "Boiled Black Beans", "grams": 100, "calories": 132.0, "protein": 8.9, "carbs": 23.7, "fat": 0.5, "safe": True}
    ]

# ------------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS
# ------------------------------------------------------------------------------

with st.sidebar:
    st.title("🥗 NutriScan AI")
    st.caption("Edge Dietary Screening & Macro Auditor")
    st.markdown("---")

    selected_diet = st.selectbox(
        "Active Dietary Restriction",
        ["vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free"],
        index=0
    )

    st.subheader("Daily Goals")
    calorie_goal = st.number_input("Calorie Target (kcal)", value=2000, step=50)
    protein_goal = st.number_input("Protein Target (g)", value=130, step=5)
    carbs_goal = st.number_input("Carbs Target (g)", value=220, step=5)
    fat_goal = st.number_input("Fat Target (g)", value=65, step=5)

    st.markdown("---")
    if st.button("Reset Daily Logs", use_container_width=True):
        st.session_state.daily_logs = []
        st.rerun()

# ------------------------------------------------------------------------------
# 4. TOP METRICS STRIP
# ------------------------------------------------------------------------------

total_cal = sum(item["calories"] for item in st.session_state.daily_logs)
total_pro = sum(item["protein"] for item in st.session_state.daily_logs)
total_carb = sum(item["carbs"] for item in st.session_state.daily_logs)
total_fat = sum(item["fat"] for item in st.session_state.daily_logs)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Calories", f"{total_cal:.0f} / {calorie_goal} kcal", f"{total_cal - calorie_goal:+.0f}")
m2.metric("Protein", f"{total_pro:.1f} / {protein_goal} g", f"{total_pro - protein_goal:+.1f}")
m3.metric("Carbs", f"{total_carb:.1f} / {carbs_goal} g", f"{total_carb - carbs_goal:+.1f}")
m4.metric("Fat", f"{total_fat:.1f} / {fat_goal} g", f"{total_fat - fat_goal:+.1f}")

st.markdown("---")

# ------------------------------------------------------------------------------
# 5. IMAGE-BASED DIETARY CHECK
# ------------------------------------------------------------------------------

tab_text, tab_scan, tab_logs = st.tabs([
    "🔍 Text food check",
    "📷 Check a meal photo",
    "📊 Today's Intake Log"
])

with tab_text:
    st.subheader("Text food restriction check")
    st.write(f"Enter a food or dish to check it against your selected **{selected_diet.title()}** category.")
    with st.form("text_food_check"):
        query_food = st.text_input(
            "Food or dish name",
            placeholder="e.g. paneer tikka, chicken salad, almond milk",
        )
        check_text = st.form_submit_button("Check food", type="primary")

    if check_text:
        if not query_food.strip():
            st.warning("Enter a food or dish name first.")
        else:
            guard = get_diet_guard()
            if guard is None:
                st.error("The dietary checker could not start. Check the local model and diet rules.")
            else:
                with st.spinner("Checking the food against your selected category…"):
                    verdict = guard.evaluate_food(query_food.strip(), selected_diet)
                    nutrition = query_food_nutrition(query_food.strip())
                st.session_state.text_check_result = {
                    "name": query_food.strip(),
                    "diet": selected_diet,
                    "verdict": verdict.to_dict(),
                    "nutrition": nutrition,
                }

    text_result = st.session_state.get("text_check_result")
    if text_result:
        if text_result["diet"] != selected_diet:
            st.info("The selected category changed. Check the food again for the new category.")
        else:
            verdict = text_result["verdict"]
            nutrition = text_result["nutrition"]
            if not verdict["safe"]:
                st.error(f"Potential conflict with {selected_diet}: {verdict['reason']}")
            elif verdict["source"] == "offline_fallback":
                st.warning(f"The result could not be fully verified: {verdict['reason']}")
            else:
                st.success(f"No detected conflict with {selected_diet}.")
            st.write(f"**Food:** {text_result['name']}")
            st.write(f"**Check details:** {verdict['reason']}")
            st.caption(f"Screening source: {verdict['source']}")
            st.caption(
                f"Nutrition per 100 g (source: {nutrition.get('source', 'fallback')}): "
                f"{nutrition['calories']:.0f} kcal · {nutrition['protein']:.1f} g protein · "
                f"{nutrition['carbs']:.1f} g carbs · {nutrition['fat']:.1f} g fat"
            )
            grams = st.number_input(
                "Portion to add to today's log (g)", min_value=1, max_value=10000,
                value=150, key="text_log_grams",
            )
            if st.button("Add checked food to today's log", key="add_text_food"):
                scale = grams / 100.0
                st.session_state.daily_logs.append({
                    "name": text_result["name"],
                    "grams": grams,
                    "calories": round(nutrition["calories"] * scale, 1),
                    "protein": round(nutrition["protein"] * scale, 1),
                    "carbs": round(nutrition["carbs"] * scale, 1),
                    "fat": round(nutrition["fat"] * scale, 1),
                    "safe": verdict["safe"],
                })
                st.success("Food added to today's intake log.")
                st.rerun()

with tab_scan:
    st.subheader("Meal photo dietary check")
    st.write(
        f"Upload a meal photo. NutriScan will identify visible foods and check them "
        f"against your selected **{selected_diet.title()}** category."
    )
    st.caption(
        f"Vision model: `{os.getenv('NUTRISCAN_MODEL', 'gemma4:e2b')}` · "
        f"Ollama endpoint: `{os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')}`"
    )
    uploaded_file = st.file_uploader(
        "Upload a meal photo",
        type=["jpg", "jpeg", "png", "webp"],
        key="meal_photo_upload",
    )

    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file).convert("RGB")
            st.image(image, caption="Selected meal photo", use_container_width=True)
        except Exception as exc:
            st.error(f"This image could not be opened: {exc}")
            image = None

        image_bytes = uploaded_file.getvalue()
        image_id = hashlib.sha256(image_bytes).hexdigest()
        if st.session_state.get("scan_image_id") != image_id:
            st.session_state.scan_image_id = image_id
            st.session_state.scan_result = None

        if image is not None and st.button(
            "Analyze image and check category", type="primary", use_container_width=True
        ):
            image_suffix = Path(uploaded_file.name).suffix.lower() or ".jpg"
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=image_suffix, delete=False) as image_file:
                    image_file.write(image_bytes)
                    temp_path = image_file.name

                with st.spinner("Identifying foods in the image with the local vision model…"):
                    extraction = extract_plate_items(temp_path)

                if not extraction.success:
                    st.session_state.scan_result = None
                    st.error(
                        extraction.error_message
                        or "The vision model could not identify foods in this image."
                    )
                elif not extraction.items:
                    st.session_state.scan_result = None
                    st.warning("No foods were detected. Try a clearer photo with the plate visible.")
                else:
                    guard = get_diet_guard()
                    if guard is None:
                        st.session_state.scan_result = None
                        st.error("The dietary checker could not start. Check the local model and diet rules.")
                    else:
                        results = []
                        for item in extraction.items:
                            verdict = guard.evaluate_food(item.name, selected_diet)
                            nutrition = query_food_nutrition(item.name)
                            grams = max(1, float(item.estimated_grams))
                            scale = grams / 100.0
                            results.append({
                                "name": item.name,
                                "grams": grams,
                                "calories": round(nutrition["calories"] * scale, 1),
                                "protein": round(nutrition["protein"] * scale, 1),
                                "carbs": round(nutrition["carbs"] * scale, 1),
                                "fat": round(nutrition["fat"] * scale, 1),
                                "safe": verdict.safe,
                                "verified": verdict.source != "offline_fallback",
                                "reason": verdict.reason,
                                "source": verdict.source,
                                "nutrition_source": nutrition.get("source", "fallback"),
                            })
                        st.session_state.scan_result = {
                            "image_id": image_id,
                            "diet": selected_diet,
                            "foods": results,
                        }
            except Exception as exc:
                st.session_state.scan_result = None
                st.error(f"Image analysis failed: {exc}")
            finally:
                if temp_path:
                    Path(temp_path).unlink(missing_ok=True)

    scan_result = st.session_state.get("scan_result")
    if scan_result:
        if scan_result["image_id"] != st.session_state.get("scan_image_id"):
            st.info("The photo changed. Analyze the current image to refresh this result.")
        elif scan_result["diet"] != selected_diet:
            st.warning("Your selected category changed. Analyze the photo again to check against it.")
        else:
            foods = scan_result["foods"]
            all_safe = all(food["safe"] and food["verified"] for food in foods)
            has_conflict = any(not food["safe"] for food in foods)
            if all_safe:
                st.success(f"No detected food conflicts with the {selected_diet} category.")
            elif has_conflict:
                st.error(f"Potential {selected_diet} restriction conflict detected in this image.")
            else:
                st.warning(
                    f"The {selected_diet} check could not fully verify these foods. "
                    "Review ingredients before relying on this result."
                )

            st.dataframe(
                [{
                    "Detected food": food["name"],
                    "Estimated portion": f"{food['grams']:.0f} g",
                    "Category check": (
                        "⚠️ Unverified" if not food["verified"]
                        else "✅ No conflict detected" if food["safe"]
                        else "⚠️ Review ingredients"
                    ),
                    "Calories (estimate)": food["calories"],
                    "Protein (g)": food["protein"],
                    "Carbs (g)": food["carbs"],
                    "Fat (g)": food["fat"],
                } for food in foods],
                use_container_width=True,
                hide_index=True,
            )
            for food in foods:
                if not food["safe"] or not food["verified"]:
                    st.warning(f"{food['name']}: {food['reason']}")
            st.caption(
                "Diet checks use detected dish names and cannot confirm hidden ingredients or "
                "cross-contamination. Nutrition may use fallback values when a dish is absent "
                "from food_data.db."
            )

            logged_id = st.session_state.get("logged_scan_id")
            if logged_id == scan_result["image_id"]:
                st.info("These detected foods have already been added to today's log.")
            elif st.button("Add detected foods to today's log", key="log_detected_foods"):
                for food in foods:
                    st.session_state.daily_logs.append({
                        "name": food["name"],
                        "grams": food["grams"],
                        "calories": food["calories"],
                        "protein": food["protein"],
                        "carbs": food["carbs"],
                        "fat": food["fat"],
                        "safe": food["safe"],
                    })
                st.session_state.logged_scan_id = scan_result["image_id"]
                st.success("Detected foods added to today's intake log.")
                st.rerun()

# ------------------------------------------------------------------------------
# 6. DAILY LOG & VISUALS
# ------------------------------------------------------------------------------
with tab_logs:
    st.subheader(f"Nutrition Log - {datetime.date.today().strftime('%B %d, %Y')}")
    if st.session_state.daily_logs:
        c_table, c_chart = st.columns([3, 2])
        with c_table:
            st.dataframe(
                [
                    {
                        "Food Item": x["name"],
                        "Weight": f"{x['grams']}g",
                        "Calories": f"{x['calories']} kcal",
                        "Protein": f"{x['protein']}g",
                        "Carbs": f"{x['carbs']}g",
                        "Fat": f"{x['fat']}g",
                        "Status": "✅ Safe" if x["safe"] else "❌ Flagged"
                    }
                    for x in st.session_state.daily_logs
                ],
                use_container_width=True
            )
        with c_chart:
            fig = go.Figure(data=[go.Pie(
                labels=["Protein", "Carbs", "Fats"],
                values=[max(0.1, total_pro * 4), max(0.1, total_carb * 4), max(0.1, total_fat * 9)],
                hole=0.55,
                marker_colors=["#3498db", "#2ecc71", "#f39c12"]
            )])
            fig.update_layout(title_text="Calorie Split (kcal)", height=260, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No meals logged yet today.")
