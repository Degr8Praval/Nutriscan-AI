"""
app.py - NutriScan & DietGuard Interactive Web Dashboard
Hacktoberfest 2026 - Edge Dietary Auditor
"""

import os
import json
import sqlite3
import datetime
import streamlit as st
import plotly.graph_objects as go
from PIL import Image

# 1. Page Config MUST be the very first Streamlit call
st.set_page_config(
    page_title="NutriScan AI - Edge Dietary Auditor",
    page_icon="🥗",
    layout="wide"
)

# ------------------------------------------------------------------------------
# 2. LOCAL DATA & ENGINE INITIALIZATION
# ------------------------------------------------------------------------------

DB_PATH = "food_data.db"
RULES_PATH = "diet_rules.json"

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
# 5. MAIN NAVIGATION TABS
# ------------------------------------------------------------------------------

tab_check, tab_scan, tab_logs = st.tabs([
    "🔍 Real-Time Food Classifier",
    "📷 Multimodal Plate Scan",
    "📊 Today's Intake Log"
])

# TAB 1: INSTANT CLASSIFIER
with tab_check:
    st.subheader("Instant Dietary Compliance Checker")
    st.write(f"Screening against constraint: **{selected_diet.title()}**")

    col_input, col_action = st.columns([4, 1])
    with col_input:
        query_food = st.text_input(
            "Dish name or ingredient:",
            placeholder="e.g. Paneer Makhani, Pad Thai, Warm Roti, Almond Milk",
            label_visibility="collapsed"
        )
    with col_action:
        run_check = st.button("Audit Food", use_container_width=True, type="primary")

    if run_check and query_food.strip():
        guard = get_diet_guard()
        
        with st.spinner("Evaluating food safety..."):
            if guard is not None:
                verdict = guard.evaluate_food(query_food, selected_diet)
            else:
                verdict = None
            nutr = query_food_nutrition(query_food)

        if verdict and verdict.safe:
            st.success(f"### ✅ SAFE FOR {selected_diet.upper()}")
        elif verdict and not verdict.safe:
            st.error(f"### ❌ VIOLATION FLAGGED FOR {selected_diet.upper()}")
        else:
            st.warning("Evaluated with fallback rules.")

        res_col1, res_col2 = st.columns([3, 2])
        with res_col1:
            if verdict:
                st.write(f"**Explanation:** {verdict.reason}")
                st.write(f"**Engine Tier:** `{verdict.source}`")
                st.write(f"**Confidence:** `{int(verdict.confidence * 100)}%`")
                if verdict.flagged_ingredients:
                    st.write(f"**Flagged Ingredients:** {', '.join(verdict.flagged_ingredients)}")

        with res_col2:
            st.caption(f"Macros per 100g (Source: {nutr.get('source', 'default')}):")
            st.write(f"- Calories: **{nutr['calories']} kcal**")
            st.write(f"- Protein: **{nutr['protein']}g** | Carbs: **{nutr['carbs']}g** | Fat: **{nutr['fat']}g**")

        st.markdown("---")
        log_col1, log_col2 = st.columns([2, 1])
        with log_col1:
            log_grams = st.slider("Portion weight (g):", 25, 500, 150, 25)
        with log_col2:
            st.write("")
            if st.button("➕ Add to Daily Log", use_container_width=True):
                scale = log_grams / 100.0
                st.session_state.daily_logs.append({
                    "name": query_food.title(),
                    "grams": log_grams,
                    "calories": round(nutr["calories"] * scale, 1),
                    "protein": round(nutr["protein"] * scale, 1),
                    "carbs": round(nutr["carbs"] * scale, 1),
                    "fat": round(nutr["fat"] * scale, 1),
                    "safe": verdict.safe if verdict else True
                })
                st.success(f"Added {log_grams}g of {query_food.title()}!")
                st.rerun()

# TAB 2: MULTIMODAL SCAN
with tab_scan:
    st.subheader("Multimodal Meal Plate Auditor")
    uploaded_file = st.file_uploader("Upload plate image", type=["jpg", "jpeg", "png"])

    col_img, col_audit = st.columns([1, 1])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        with col_img:
            st.image(image, caption="Plate Snapshot", use_container_width=True)

        with col_audit:
            st.write("### AI Food Extraction")
            c1, c2 = st.columns(2)
            i1 = c1.text_input("Item 1", value="Grilled Chicken")
            g1 = c2.number_input("Grams", value=150, step=25, key="g1")

            c3, c4 = st.columns(2)
            i2 = c3.text_input("Item 2", value="Steamed Rice")
            g2 = c4.number_input("Grams", value=200, step=25, key="g2")

            if st.button("🚀 Audit & Log Plate", type="primary", use_container_width=True):
                guard = get_diet_guard()
                for name, g in [(i1, g1), (i2, g2)]:
                    nutr = query_food_nutrition(name)
                    scale = g / 100.0
                    v = guard.evaluate_food(name, selected_diet) if guard else None
                    st.session_state.daily_logs.append({
                        "name": name.title(),
                        "grams": g,
                        "calories": round(nutr["calories"] * scale, 1),
                        "protein": round(nutr["protein"] * scale, 1),
                        "carbs": round(nutr["carbs"] * scale, 1),
                        "fat": round(nutr["fat"] * scale, 1),
                        "safe": v.safe if v else True
                    })
                st.rerun()

# TAB 3: DAILY LOG & VISUALS
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