"""
test_diet_guard.py - Comprehensive Test & Benchmark Suite for DietGuard
Tests:
1. Deterministic Tier 1 checks (meat, poultry, dairy, gluten, nuts).
2. Override rules (complex dishes with hidden allergens).
3. Live LLM Tier 2 fallback with qwen2.5:1.5b.
4. Batch meal evaluation (multi-item payload from vision pipeline).
5. Robustness against malformed inputs, punctuation, casing, and noise.
6. Execution latency benchmarking.
"""

import time
import sys
from typing import List, Dict, Any, Tuple
from diet_guard import DietGuard, DietaryVerdict

# ANSI formatting helpers for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"{BOLD}{CYAN}{title.center(75)}{RESET}")
    print("=" * 75)


def run_test_suite():
    print_banner("INITIALIZING DIETGUARD TEST SUITE (qwen2.5:1.5b)")
    
    start_init = time.perf_counter()
    guard = DietGuard(config_path="diet_rules.json", model="qwen2.5:1.5b")
    init_time = (time.perf_counter() - start_init) * 1000
    print(f"[*] Engine initialization & rule indexing took: {init_time:.2f} ms\n")

    total_tests = 0
    passed_tests = 0

    # ==========================================================================
    # TEST SUITE 1: DETERMINISTIC TIER 1 CHECKS (Expected Fast Rule Matches)
    # Format: (food_name, diet, expected_safe, category_description)
    # ==========================================================================
    print_banner("SUITE 1: DETERMINISTIC KEYWORD BLACKLIST CHECKS")
    tier1_cases = [
        # Vegetarian tests
        ("Grilled Chicken Breast", "vegetarian", False, "Poultry violation"),
        ("Beef Sirloin Steak", "vegetarian", False, "Red meat violation"),
        ("Atlantic Salmon Fillet", "vegetarian", False, "Fish violation"),
        ("Crispy Bacon Strips", "vegetarian", False, "Pork violation"),
        ("Steamed Basmati Rice", "vegetarian", True, "Safe staple"),
        ("Broccoli and Tofu Stir Fry", "vegetarian", True, "Plant protein safe"),
        
        # Vegan tests
        ("Fresh Paneer Cubes", "vegan", False, "Dairy violation"),
        ("Scrambled Whole Eggs", "vegan", False, "Egg violation"),
        ("Butter Croissant", "vegan", False, "Dairy butter violation"),
        ("Whole Milk Latte", "vegan", False, "Cow milk violation"),
        ("Boiled Black Beans", "vegan", True, "Legume safe"),
        ("Pure Maple Syrup", "vegan", True, "Sweetener safe"),
        
        # Gluten-Free tests
        ("Whole Wheat Sourdough Bread", "gluten-free", False, "Wheat bread violation"),
        ("Hot Garlic Naan", "gluten-free", False, "Wheat naan violation"),
        ("Fresh Chapati Roti", "gluten-free", False, "Atta flour violation"),
        ("Semolina Sooji Halwa", "gluten-free", False, "Semolina grain violation"),
        ("Gluten-Free Rolled Oats", "gluten-free", True, "Labeled GF safe"),
        ("Boiled Red Potatoes", "gluten-free", True, "Tubers safe"),

        # Nut-Free & Dairy-Free tests
        ("Roasted Salted Cashews", "nut-free", False, "Tree nut violation"),
        ("Creamy Peanut Butter", "nut-free", False, "Peanut violation"),
        ("Sunflower Seed Butter", "nut-free", True, "Seed safe"),
        ("Greek Yogurt Dip", "dairy-free", False, "Yogurt dairy violation"),
        ("Almond Milk Unsweetened", "dairy-free", True, "Plant milk safe"),
    ]

    for food, diet, expected, desc in tier1_cases:
        total_tests += 1
        t0 = time.perf_counter()
        verdict = guard.evaluate_food(food, diet)
        dt = (time.perf_counter() - t0) * 1000

        is_correct = (verdict.safe == expected)
        if is_correct:
            passed_tests += 1
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        expected_tag = "SAFE" if expected else "UNSAFE"
        actual_tag = "SAFE" if verdict.safe else "UNSAFE"
        print(f"[{status}] {food:<28} | Diet: {diet:<12} | Exp: {expected_tag:<6} Got: {actual_tag:<6} | {dt:6.2f}ms | {desc}")

    # ==========================================================================
    # TEST SUITE 2: OVERRIDE DICTIONARY (Hidden Allergens in Complex Dishes)
    # ==========================================================================
    print_banner("SUITE 2: COMPLEX DISH OVERRIDE TESTS")
    override_cases = [
        ("Traditional Pad Thai", "vegetarian", False, "Contains fish sauce / dried shrimp"),
        ("Traditional Pad Thai", "vegan", False, "Contains egg and fish sauce"),
        ("Classic Caesar Salad", "vegetarian", False, "Contains blended anchovies"),
        ("Classic Caesar Salad", "vegan", False, "Contains parmesan and egg yolks"),
        ("Restaurant Dal Makhani", "vegan", False, "Contains heavy butter and cream"),
        ("Spicy Paneer Tikka", "dairy-free", False, "Paneer is cow milk cheese"),
    ]

    for food, diet, expected, desc in override_cases:
        total_tests += 1
        t0 = time.perf_counter()
        verdict = guard.evaluate_food(food, diet)
        dt = (time.perf_counter() - t0) * 1000

        is_correct = (verdict.safe == expected and verdict.source == "rule_engine")
        if is_correct:
            passed_tests += 1
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        print(f"[{status}] {food:<28} | Diet: {diet:<12} | {verdict.reason} ({dt:.2f}ms)")

    # ==========================================================================
    # TEST SUITE 3: LLM REASONING PATH (qwen2.5:1.5b Verification)
    # Dishes not overtly matching single keywords that require culinary inference
    # ==========================================================================
    print_banner("SUITE 3: LIVE LOCAL LLM INFERENCE (qwen2.5:1.5b)")
    llm_cases = [
        ("Steamed Edamame in Sea Salt", "vegan", True, "Soybeans and salt only"),
        ("Chicken Quesadilla", "vegetarian", False, "Mixed poultry wrap"),
        ("Shrimp Tempura Roll", "vegetarian", False, "Seafood wrapped in sushi rice"),
        ("Beef Bolognese Tagliatelle", "gluten-free", False, "Wheat pasta with minced meat"),
    ]

    for food, diet, expected, desc in llm_cases:
        total_tests += 1
        print(f"[*] Querying qwen2.5:1.5b for '{food}' on {diet} diet...", end="", flush=True)
        t0 = time.perf_counter()
        verdict = guard.evaluate_food(food, diet)
        dt = (time.perf_counter() - t0) * 1000

        is_correct = (verdict.safe == expected)
        if is_correct:
            passed_tests += 1
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        print(f"\r[{status}] {food:<28} | Diet: {diet:<12} | Source: {verdict.source:<20} | Latency: {dt:7.1f}ms")
        print(f"       └── Reason: {verdict.reason}")

    # ==========================================================================
    # TEST SUITE 4: STRING NORMALIZATION & DIRTY INPUT ROBUSTNESS
    # ==========================================================================
    print_banner("SUITE 4: DIRTY INPUT & PUNCTUATION ROBUSTNESS")
    dirty_cases = [
        ("CHICKEN BREAST (EXTRA CRISPY!!!)", "vegetarian", False, "Uppercase & punctuation"),
        ("  paneer   makhani  ", "vegan", False, "Irregular whitespace"),
        ("wheat-flour chapati!!", "gluten-free", False, "Hyphenated keyword with symbols"),
        ("steamed.... white... rice???", "vegan", True, "Excessive punctuation safe staple"),
    ]

    for food, diet, expected, desc in dirty_cases:
        total_tests += 1
        verdict = guard.evaluate_food(food, diet)
        is_correct = (verdict.safe == expected)
        if is_correct:
            passed_tests += 1
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"
        print(f"[{status}] Raw Input: '{food}' -> Matched: safe={verdict.safe} ({desc})")

    # ==========================================================================
    # TEST SUITE 5: BATCH MEAL EVALUATION (Simulating Vision Pipeline Payload)
    # ==========================================================================
    print_banner("SUITE 5: BATCH MEAL AUDITING (Hacker 1 Vision Output Simulation)")
    mock_meal = [
        {"name": "Steamed Jasmine Rice", "grams": 200},
        {"name": "Crispy Spiced Tofu", "grams": 150},
        {"name": "Steamed Broccoli Florets", "grams": 100},
        {"name": "Butter Chicken Gravy", "grams": 80}
    ]

    print("[*] Feeding mock 4-item plate into guard for a VEGAN diet...")
    batch_start = time.perf_counter()
    report = guard.evaluate_meal(mock_meal, diet="vegan")
    batch_dt = (time.perf_counter() - batch_start) * 1000

    print(f"[*] Batch Audit Complete in {batch_dt:.2f}ms")
    print(f"    Meal Safe Verdict:  {GREEN if report['meal_safe'] else RED}{report['meal_safe']}{RESET}")
    print(f"    Total Plate Items:  {report['total_items']}")
    print(f"    Flagged Violations: {report['flagged_count']}")
    print(f"    Violating Elements: {report['all_flagged_ingredients']}")
    print("\n    Individual Item Breakdown:")
    for item_v in report["item_verdicts"]:
        icon = f"{GREEN}✓{RESET}" if item_v["safe"] else f"{RED}✗{RESET}"
        print(f"      [{icon}] {item_v['food']:<25} -> {item_v['reason']}")

    total_tests += 1
    if not report["meal_safe"] and report["flagged_count"] >= 1:
        passed_tests += 1
        print(f"\n[{GREEN}PASS{RESET}] Batch meal auditing correctly identified non-compliant ingredients.")
    else:
        print(f"\n[{RED}FAIL{RESET}] Batch meal auditing failed to flag violations.")

    # ==========================================================================
    # FINAL SUMMARY REPORT
    # ==========================================================================
    print_banner("TEST EXECUTION SCORECARD")
    pass_pct = (passed_tests / total_tests) * 100
    color = GREEN if pass_pct == 100 else YELLOW if pass_pct >= 85 else RED
    
    print(f"Total Tests Run: {total_tests}")
    print(f"Passed Tests:    {passed_tests}")
    print(f"Failed Tests:    {total_tests - passed_tests}")
    print(f"Success Rate:    {color}{BOLD}{pass_pct:.1f}%{RESET}")
    print("=" * 75 + "\n")

    if passed_tests == total_tests:
        print(f"{GREEN}{BOLD}ALL SYSTEMS VERIFIED. DietGuard is ready for Hacker 4 CLI wiring!{RESET}\n")
    else:
        print(f"{YELLOW}A few tests did not match expectations. Check failure items above.{RESET}\n")


if __name__ == "__main__":
    run_test_suite()