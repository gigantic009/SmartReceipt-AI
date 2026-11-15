"""Explainable baseline expense categorization.

This is a deterministic starter taxonomy, not a trained classifier. Categories
are suggestions and should remain editable by the user.
"""
import re

RULES = [
    ("Travel", (r"hotel", r"airline", r"flight", r"railway", r"train", r"taxi", r"uber", r"ola", r"parking", r"fuel", r"petrol")),
    ("Food & Dining", (r"restaurant", r"cafe", r"coffee", r"food", r"breakfast", r"lunch", r"dinner", r"bakery")),
    ("Groceries", (r"grocery", r"supermarket", r"mart", r"whole foods", r"vegetable", r"provision")),
    ("Shopping", (r"retail", r"store", r"fashion", r"clothing", r"electronics", r"amazon", r"flipkart")),
    ("Utilities", (r"electricity", r"water bill", r"gas bill", r"broadband", r"internet", r"mobile recharge")),
    ("Healthcare", (r"hospital", r"clinic", r"pharmacy", r"medical", r"diagnostic", r"laboratory")),
    ("Office & Software", (r"software", r"cloud", r"hosting", r"subscription", r"office supplies")),
]


def suggest_category(merchant: str | None, source_text: str = "") -> dict:
    haystack = f"{merchant or ''}\n{source_text[:3000]}".casefold()
    for category, patterns in RULES:
        if any(re.search(pattern, haystack, re.I) for pattern in patterns):
            return {"category": category, "confidence": "low", "method": "keyword_suggestion"}
    return {"category": "Uncategorized", "confidence": "unknown", "method": "fallback"}
