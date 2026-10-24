"""
diet_guard.py - Context-Injected Dietary Restriction Classifier
Supports dynamic safe_prefixes loaded from diet_rules.json
"""

import sys
import os
import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from .embedding_classifier import SemanticDietClassifier
    SEMANTIC_AVAILABLE = True
except ImportError:
    try:
        from embedding_classifier import SemanticDietClassifier
        SEMANTIC_AVAILABLE = True
    except ImportError:
        SEMANTIC_AVAILABLE = False


@dataclass
class DietaryVerdict:
    food: str
    diet: str
    safe: bool
    confidence: float
    reason: str
    flagged_ingredients: List[str]
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DietGuard:
    def __init__(self, config_path: str = "diet_rules.json", model: str | None = None):
        self.model = model or os.getenv("NUTRISCAN_MODEL", "gemma4:e2b")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(base_dir, config_path)
        
        self.rules: Dict[str, Any] = {}
        self.overrides: Dict[str, Any] = {}
        self.safe_prefixes: Dict[str, List[str]] = {}
        self._load_config()

        self.semantic_engine = None
        if SEMANTIC_AVAILABLE:
            try:
                self.semantic_engine = SemanticDietClassifier(config_path=self.config_path)
            except Exception:
                pass

    def _load_config(self):
        """Loads restrictions, dish overrides, and safe prefixes from JSON."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.rules = data.get("restrictions", {})
                    self.overrides = data.get("dish_overrides", {})
                    self.safe_prefixes = data.get("safe_prefixes", {})
                return
            except Exception:
                pass
        self._load_fallback_rules()

    def _load_fallback_rules(self):
        """In-memory fallback if diet_rules.json is absent."""
        self.rules = {
            "vegetarian": {
                "forbidden_keywords": [
                    "chicken", "beef", "pork", "lamb", "mutton", "turkey", "duck",
                    "bacon", "ham", "sausage", "pepperoni", "salami", "fish",
                    "salmon", "tuna", "shrimp", "crab", "lobster", "gelatin", "lard"
                ]
            },
            "vegan": {
                "forbidden_keywords": [
                    "chicken", "beef", "pork", "fish", "shrimp", "milk", "cheese",
                    "butter", "cream", "paneer", "ghee", "yogurt", "whey", "egg",
                    "eggs", "mayo", "honey", "gelatin"
                ]
            },
            "gluten-free": {
                "forbidden_keywords": [
                    "wheat", "barley", "rye", "flour", "bread", "toast", "pasta",
                    "noodle", "roti", "chapati", "naan", "paratha", "seitan", "semolina", "sooji", "atta"
                ]
            },
            "dairy-free": {
                "forbidden_keywords": [
                    "milk", "cheese", "butter", "cream", "paneer", "ghee", "yogurt", "curd", "whey"
                ]
            },
            "nut-free": {
                "forbidden_keywords": [
                    "almond", "walnut", "cashew", "pistachio", "pecan", "peanut", "peanut butter"
                ]
            }
        }
        self.safe_prefixes = {
            "dairy-free": ["almond milk", "soy milk", "oat milk", "coconut milk", "cashew milk"],
            "vegan": ["almond milk", "soy milk", "oat milk", "coconut milk", "cashew milk"],
            "gluten-free": ["gluten-free", "gluten free"],
            "nut-free": ["sunflower seed butter", "sunflower butter"]
        }
        self.overrides = {
            "pad thai": {
                "vegetarian": {"safe": False, "reason": "Traditionally prepared with fish sauce and dried shrimp.", "flags": ["fish sauce", "shrimp"]},
                "vegan": {"safe": False, "reason": "Contains fish sauce and scrambled egg.", "flags": ["fish sauce", "egg"]}
            },
            "caesar salad": {
                "vegetarian": {"safe": False, "reason": "Traditional Caesar dressing contains blended anchovies.", "flags": ["anchovies"]},
                "vegan": {"safe": False, "reason": "Contains parmesan cheese and eggs in dressing.", "flags": ["parmesan", "egg"]}
            },
            "dal makhani": {
                "vegan": {"safe": False, "reason": "Prepared with significant butter and heavy cream.", "flags": ["butter", "cream"]},
                "dairy-free": {"safe": False, "reason": "Contains butter and heavy cream.", "flags": ["butter", "cream"]}
            },
            "paneer tikka": {
                "vegan": {"safe": False, "reason": "Paneer is cow milk cheese.", "flags": ["paneer"]},
                "dairy-free": {"safe": False, "reason": "Paneer is dairy cheese.", "flags": ["paneer"]}
            }
        }

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-z0-9\-]+\b", text.lower())

    def _check_rules(self, food_name: str, norm_diet: str) -> Optional[DietaryVerdict]:
        clean_food = food_name.lower().strip()

        # 1. Check Dynamic Safe Prefixes / Exceptions from JSON
        exceptions = self.safe_prefixes.get(norm_diet, [])
        for exc in exceptions:
            if exc in clean_food:
                return DietaryVerdict(
                    food=food_name,
                    diet=norm_diet,
                    safe=True,
                    confidence=0.99,
                    reason=f"Recognized safe variant: '{exc}'.",
                    flagged_ingredients=[],
                    source="rule_engine"
                )

        # 2. Check Complex Dish Overrides
        for dish, diet_rules in self.overrides.items():
            if dish in clean_food and norm_diet in diet_rules:
                rule = diet_rules[norm_diet]
                return DietaryVerdict(
                    food=food_name,
                    diet=norm_diet,
                    safe=rule["safe"],
                    confidence=1.0,
                    reason=rule["reason"],
                    flagged_ingredients=rule.get("flags", []),
                    source="rule_engine"
                )

        # 3. Check Keyword Blacklist
        diet_config = self.rules.get(norm_diet, {})
        forbidden_keywords = diet_config.get("forbidden_keywords", [])
        tokens = set(self._tokenize(clean_food))

        flagged = []
        for kw in forbidden_keywords:
            if " " in kw and kw in clean_food:
                flagged.append(kw)
            elif kw in tokens:
                flagged.append(kw)

        if flagged:
            return DietaryVerdict(
                food=food_name,
                diet=norm_diet,
                safe=False,
                confidence=0.98,
                reason=f"Violates {norm_diet} diet: contains {', '.join(sorted(set(flagged)))}.",
                flagged_ingredients=list(set(flagged)),
                source="rule_engine"
            )

        return None

    def evaluate_food(self, food_name: str, diet: str) -> DietaryVerdict:
        norm_diet = diet.lower().strip().replace(" ", "-")

        # 1. Tier 1: Rules & Overrides (< 1ms)
        rule_verdict = self._check_rules(food_name, norm_diet)
        if rule_verdict is not None:
            return rule_verdict

        # 2. Tier 2: Semantic Embedding Match (< 10ms)
        if self.semantic_engine is not None:
            safe, score, reason = self.semantic_engine.evaluate(food_name, norm_diet, threshold=0.72)
            if not safe:
                matched_kw = reason.split("'")[-2] if "'" in reason else "allergen"
                return DietaryVerdict(
                    food=food_name,
                    diet=norm_diet,
                    safe=False,
                    confidence=round(score, 2),
                    reason=reason,
                    flagged_ingredients=[matched_kw],
                    source="embedding_classifier"
                )

        # 3. Tier 3: LLM Fallback (qwen2.5:1.5b)
        if OLLAMA_AVAILABLE:
            llm_res = self._query_llm_with_context(food_name, norm_diet, self.rules.get(norm_diet, {}))
            if llm_res is not None:
                return llm_res

        # 4. Safe Default
        return DietaryVerdict(
            food=food_name,
            diet=norm_diet,
            safe=True,
            confidence=0.80,
            reason=f"No overt {norm_diet} ingredients found in '{food_name}'.",
            flagged_ingredients=[],
            source="offline_fallback"
        )

    def _query_llm_with_context(self, food_name: str, diet: str, diet_config: dict) -> Optional[DietaryVerdict]:
        """
        Asks LLM for components WITHOUT exposing forbidden keyword lists,
        then deterministically verifies them in Python.
        """
        clean_name = food_name.lower().strip()

        # Step 1: Prompt ONLY for factual ingredients (no negative examples)
        prompt = (
            f"List the 3 to 6 primary ingredients traditionally used to make '{food_name}'.\n"
            f"Return JSON only: {{\"ingredients\": [\"ingredient1\", \"ingredient2\", \"ingredient3\"]}}"
        )

        try:
            res = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.0}
            )
            raw = res["message"]["content"].strip()
            data = json.loads(raw)

            extracted = [str(item).lower().strip() for item in data.get("ingredients", [])]
            if not extracted:
                extracted = [clean_name]

            # Step 2: Deterministic verification in Python
            forbidden_keywords = diet_config.get("forbidden_keywords", [])
            flagged = []

            for ing in extracted:
                tokens = set(re.findall(r"\b\w+\b", ing))
                for kw in forbidden_keywords:
                    # Match exact words or compound phrases (e.g., 'fish sauce')
                    if kw in tokens or (" " in kw and kw in ing):
                        flagged.append(kw)

            # Defensive sanity check: If dish is explicitly prefixed 'vegetable/veggie',
            # reject absurd animal hallucinations
            if any(term in clean_name for term in ["vegetable", "veggie", "plant-based"]):
                flagged = [f for f in flagged if f not in ["beef", "salmon", "fish", "chicken", "pork", "lamb"]]

            flagged = list(set(flagged))

            if flagged:
                return DietaryVerdict(
                    food=food_name,
                    diet=diet,
                    safe=False,
                    confidence=0.92,
                    reason=f"Violates {diet} diet: contains {', '.join(flagged)}.",
                    flagged_ingredients=flagged,
                    source=f"local_llm ({self.model})"
                )
            else:
                return DietaryVerdict(
                    food=food_name,
                    diet=diet,
                    safe=True,
                    confidence=0.95,
                    reason=f"Safe for {diet}. Prepared with: {', '.join(extracted[:4])}.",
                    flagged_ingredients=[],
                    source=f"local_llm ({self.model})"
                )
        except Exception:
            return None

        PLANT_EXCLUSIONS = {
        "nut", "nuts", "peanut", "peanuts", "almond", "almonds", "walnut", "walnuts",
        "cashew", "cashews", "pistachio", "pecan", "seed", "seeds", "chia", "flax",
        "rice", "grain", "oat", "oats", "bean", "beans", "lentil", "lentils", "tofu"
    }

    def evaluate(self, food_item: str, diet: str, threshold: float = 0.82) -> tuple:
        clean = food_item.lower().strip()
        
        # 1. If screening for vegetarian/vegan and the query is a recognized plant staple, skip meat similarity
        if diet in ["vegetarian", "vegan"]:
            tokens = set(re.findall(r"\b\w+\b", clean))
            if tokens.intersection(PLANT_EXCLUSIONS):
                return True, 0.0, "Recognized plant staple"

        for item in items:
            name = item.get("name", "Unknown item")
            res = self.evaluate_food(name, diet)
            verdicts.append(res)
            if not res.safe:
                is_entire_meal_safe = False
                all_flags.extend(res.flagged_ingredients)

        return {
            "diet": diet,
            "meal_safe": is_entire_meal_safe,
            "total_items": len(items),
            "flagged_count": len([v for v in verdicts if not v.safe]),
            "all_flagged_ingredients": list(set(all_flags)),
            "item_verdicts": [v.to_dict() for v in verdicts]
        }

if __name__ == "__main__":
    guard = DietGuard()

    # Handle `check` command
    if len(sys.argv) >= 3 and sys.argv[1].lower() == "check":
        food_query = sys.argv[2]
        diet_query = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "vegetarian"
        json_output = "--json" in sys.argv

        res = guard.evaluate_food(food_query, diet_query)

        if json_output:
            # Clean JSON stdout for your UI/subprocess hooks
            print(json.dumps(res.to_dict(), indent=2))
        else:
            # Human-readable ANSI terminal output
            status_tag = "\033[92m✅ SAFE\033[0m" if res.safe else "\033[91m❌ VIOLATION\033[0m"
            print("\n" + "=" * 60)
            print(f"  DIETGUARD EVALUATION REPORT")
            print("=" * 60)
            print(f"  Query:      {res.food}")
            print(f"  Diet:       {res.diet}")
            print(f"  Status:     {status_tag}")
            print(f"  Confidence: {int(res.confidence * 100)}%")
            print(f"  Engine:     {res.source}")
            print(f"  Reason:     {res.reason}")
            if res.flagged_ingredients:
                print(f"  Flagged:    {', '.join(res.flagged_ingredients)}")
            print("=" * 60 + "\n")
        sys.exit(0)

    # Fallback sanity run if no args passed
    print("\n[DietGuard] Running quick check...")
    sample = guard.evaluate_food("Paneer Makhani", "vegan")
    print(f"Test Item: Paneer Makhani (vegan) -> Safe: {sample.safe} [{sample.source}] - {sample.reason}\n")
    print("Tip: Use 'python3 diet_guard.py check \"<dish>\" <diet>' for custom queries.")
