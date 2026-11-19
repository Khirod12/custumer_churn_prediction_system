"""
Project help chatbot — clear, friendly answers about the app and retention offers.
"""
import re
from typing import Optional

from agents.offer_engine import RISK_TIERS

# Full catalog: single source for chat answers (aligned with offer_engine.py)
OFFER_CATALOG = {
    "LOYAL10": {
        "type": "coupon",
        "title": "10% Loyalty Cashback",
        "description": "Thank-you cashback on the next statement for staying with us.",
        "value": "10%",
        "when": "Low churn risk (below 30% probability).",
    },
    "PRIORITY-SUPPORT": {
        "type": "offer",
        "title": "Priority Support Line",
        "description": "Dedicated queue for account questions and quick resolutions.",
        "value": "Free upgrade",
        "when": "Low churn risk (below 30% probability).",
    },
    "STAY15": {
        "type": "coupon",
        "title": "15% Fee Waiver Coupon",
        "description": "Waive service fees on one product for the next billing cycle.",
        "value": "15%",
        "when": "Moderate risk (30–50% churn probability).",
    },
    "CHECKIN-CALL": {
        "type": "offer",
        "title": "Relationship Manager Check-in",
        "description": "Personal call to review goals and optimize your product mix.",
        "value": "Scheduled within 7 days",
        "when": "Moderate risk (30–50% churn probability).",
    },
    "SAVE25": {
        "type": "coupon",
        "title": "25% Retention Discount",
        "description": "Discount on annual maintenance or subscription fees.",
        "value": "25%",
        "when": "High risk (50–70% churn probability).",
    },
    "FLEX-PLAN": {
        "type": "offer",
        "title": "Flexible Payment Plan",
        "description": "Restructure dues with lower installments for 3 months.",
        "value": "0% setup fee",
        "when": "High risk (50–70% churn probability).",
    },
    "BONUS50": {
        "type": "coupon",
        "title": "$50 Account Credit",
        "description": "One-time credit applied when the customer remains active 60 days.",
        "value": "$50",
        "when": "High risk (50–70% churn probability).",
    },
    "VIP40": {
        "type": "coupon",
        "title": "40% VIP Retention Package",
        "description": "Maximum discount on fees plus waived penalties for one cycle.",
        "value": "40%",
        "when": "Critical risk (70% or higher churn probability).",
    },
    "EXEC-ESCALATION": {
        "type": "offer",
        "title": "Executive Retention Specialist",
        "description": "Same-day outreach from a senior retention agent.",
        "value": "Within 24 hours",
        "when": "Critical risk (70% or higher).",
    },
    "CREDIT100": {
        "type": "coupon",
        "title": "$100 Loyalty Credit",
        "description": "Immediate account credit if the customer accepts the retention bundle.",
        "value": "$100",
        "when": "Critical risk (70% or higher).",
    },
    "CUSTOM-BUNDLE": {
        "type": "offer",
        "title": "Custom Product Bundle",
        "description": "Tailored multi-product package priced below standalone products.",
        "value": "Personalized quote",
        "when": "Critical risk (70% or higher).",
    },
    "LAST-CHANCE": {
        "type": "offer",
        "title": "Last-Chance Retention Match",
        "description": "We match a competitor offer up to a capped amount after verification.",
        "value": "Up to $150",
        "when": "Critical tier only, when churn probability is 85% or above.",
    },
    "REACTIVATE20": {
        "type": "coupon",
        "title": "20% Reactivation Bonus",
        "description": "Reward for completing one transaction after re-engagement.",
        "value": "20%",
        "when": "Added when the customer is not an active member.",
    },
    "CARD-SIGNUP": {
        "type": "offer",
        "title": "Premium Card Sign-up Offer",
        "description": "No annual fee for the first year plus bonus rewards points.",
        "value": "First year free",
        "when": "Added when the customer does not have a credit card (Has Credit Card = No).",
    },
    "BUNDLE-PLUS": {
        "type": "offer",
        "title": "Multi-Product Bundle Discount",
        "description": "Add a second product at a reduced bundled rate.",
        "value": "30% off add-on",
        "when": "Added when the customer has only one product.",
    },
    "WEALTH-DESK": {
        "type": "offer",
        "title": "Dedicated Wealth Desk Access",
        "description": "Priority advisor for high-balance accounts.",
        "value": "Complimentary quarter",
        "when": "Added when account balance is above $100,000.",
    },
    "TENURE-LOYAL": {
        "type": "coupon",
        "title": "Long-Tenure Appreciation",
        "description": "Extra loyalty points for customers with 5+ years tenure.",
        "value": "500 bonus points",
        "when": "Added when tenure is 5 years or more.",
    },
}

CODE_PATTERN = re.compile(r"\b([A-Z]{2,}(?:-[A-Z0-9]+)+)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _has_phrase(q: str, phrase: str) -> bool:
    return phrase in q


def _word_match(q: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", q) for w in words)


def _find_offer_code(message: str) -> Optional[str]:
    """Detect offer/coupon code in free-text (e.g. 'CARD-SIGNUP Premium Card...')."""
    upper = message.upper()
    for code in OFFER_CATALOG:
        if code in upper:
            return code
        compact = code.replace("-", "")
        if compact in upper.replace("-", "").replace(" ", ""):
            return code
    for match in CODE_PATTERN.finditer(message):
        candidate = match.group(1).upper()
        if candidate in OFFER_CATALOG:
            return candidate
    q = _normalize(message)
    for code, meta in OFFER_CATALOG.items():
        title_norm = _normalize(meta["title"])
        if title_norm in q or q in title_norm:
            return code
        if title_norm.replace("-", " ") in q:
            return code
    return None


def _is_greeting(q: str) -> bool:
    if len(q) > 50:
        return False
    if _word_match(q, ("hi", "hello", "hey", "howdy")):
        return True
    return q in ("hi", "hello", "hey", "start", "help")


class SupportChatbot:
    """Friendly assistant for project help and retention offers."""

    def reply(self, message: str, context: Optional[dict] = None) -> str:
        if not message or not message.strip():
            return "Go ahead and type your question — I'm here to help."

        raw = message.strip()
        q = _normalize(raw)

        # Always resolve offer codes first (avoids "hi" inside "th**is**" bug)
        code = _find_offer_code(raw)
        if code:
            return self._explain_offer(code)

        if context and _word_match(
            q,
            ("my", "last", "previous"),
        ) and _word_match(q, ("offer", "coupon", "prediction", "result", "recommend")):
            return self._answer_from_context(context)

        if _is_greeting(q):
            return self._greeting()

        if _word_match(q, ("coupon", "coupons")) and _word_match(
            q, ("list", "all", "which", "available", "show")
        ):
            return self._list_offers_short()

        if _word_match(q, ("coupon", "coupons", "offer", "offers")) and _word_match(
            q, ("difference", "vs", "versus", "between")
        ):
            return self._coupon_vs_offer()

        if _word_match(q, ("tier", "tiers", "risk")) or (
            _word_match(q, ("low", "moderate", "high", "critical"))
            and _word_match(q, ("probability", "risk", "churn"))
        ):
            return self._explain_tiers()

        if _word_match(q, ("agent", "agentic", "workflow")):
            return self._explain_agents()

        if _word_match(q, ("catboost", "smote", "model", "accuracy", "feature")):
            return self._explain_model(q)

        if _word_match(q, ("churn", "predict", "prediction", "threshold", "probability")):
            return self._explain_churn(q)

        if _word_match(q, ("firebase", "database", "stored", "save")):
            return self._explain_firebase()

        if _word_match(q, ("project", "app", "website", "pages")):
            return self._explain_project()

        if _word_match(q, ("help", "what can")) and len(q) < 30:
            return self._greeting()

        return self._fallback()

    def _greeting(self) -> str:
        return (
            "Hello! I'm your ChurnAI assistant.\n\n"
            "I can explain how churn prediction works, how the retention agents choose offers, "
            "or any coupon code like **CARD-SIGNUP** or **VIP40**.\n\n"
            "Just ask in your own words — for example: "
            "*CARD-SIGNUP Premium Card tell me about this* or *What is SAVE25?*"
        )

    def _explain_offer(self, code: str) -> str:
        item = OFFER_CATALOG[code]
        kind = "Coupon" if item["type"] == "coupon" else "Offer"
        return (
            f"Here’s a clear overview of **{code}** — *{item['title']}*.\n\n"
            f"**What it is:** {item['description']}\n\n"
            f"**Benefit:** {item['value']}\n\n"
            f"**When it appears:** {item['when']}\n\n"
            f"This is a **{kind.lower()}** in our retention system. "
            f"It shows on the Predict page after the agent scores churn risk.\n\n"
            f"Want details on another code? Paste its name or code anytime."
        )

    def _answer_from_context(self, ctx: dict) -> str:
        pred = ctx.get("prediction", {})
        ret = ctx.get("retention", {})
        label = pred.get("label", "Unknown")
        prob = pred.get("probability", 0)
        tier = ret.get("risk_tier", "unknown")
        coupons = ret.get("coupons", [])
        offers = ret.get("offers", [])

        parts = [
            f"From your **last prediction** on the Predict page:\n",
            f"You were scored as **{label}** with **{prob:.1%}** churn probability "
            f"({tier} risk tier).\n",
        ]
        if coupons or offers:
            parts.append("The agent recommended:\n")
            for c in coupons:
                parts.append(f"• **{c['code']}** — {c['title']} ({c['value']})")
            for o in offers:
                parts.append(f"• **{o['code']}** — {o['title']} ({o['value']})")
            parts.append(
                "\nAsk about any code above (e.g. *tell me about SAVE25*) for a full explanation."
            )
        else:
            parts.append("No coupons or offers were listed for that run.")
        parts.append("\nRun Predict again anytime to refresh recommendations.")
        return "\n".join(parts)

    def _list_offers_short(self) -> str:
        return (
            "We have **tier-based** offers (stronger as churn risk rises) and **personalized** add-ons "
            "(inactive member, no card, one product, high balance, long tenure).\n\n"
            "Examples by tier:\n"
            "• Low → LOYAL10, PRIORITY-SUPPORT\n"
            "• Moderate → STAY15, CHECKIN-CALL\n"
            "• High → SAVE25, FLEX-PLAN, BONUS50\n"
            "• Critical → VIP40, EXEC-ESCALATION, CREDIT100, CUSTOM-BUNDLE\n\n"
            "Personalized: REACTIVATE20, CARD-SIGNUP, BUNDLE-PLUS, WEALTH-DESK, TENURE-LOYAL\n\n"
            "Paste any code (like **CARD-SIGNUP**) and I'll explain it in detail."
        )

    def _coupon_vs_offer(self) -> str:
        return (
            "Good question — here’s the simple difference:\n\n"
            "**Coupons** are discounts or credits (percent off, fee waiver, account credit). "
            "Examples: LOYAL10, SAVE25, BONUS50.\n\n"
            "**Offers** are services or experiences (a call from a manager, payment plan, "
            "executive outreach). Examples: CHECKIN-CALL, FLEX-PLAN, CARD-SIGNUP.\n\n"
            "The OfferAgent picks both based on churn probability and the customer profile."
        )

    def _explain_tiers(self) -> str:
        lines = [
            "Churn probability is grouped into **four risk tiers**. "
            "Higher risk means stronger coupons and offers:\n",
        ]
        for name, low, high in RISK_TIERS:
            hi = f"{high * 100:.0f}%" if high <= 1 else "100%"
            lines.append(f"• **{name.title()}** — {low * 100:.0f}% to {hi}")
        lines.append(
            "\nIf probability is above **50%**, the label is **Churn**; otherwise **No Churn**. "
            "Offers can still appear for lower labels when risk is elevated (preventive retention)."
        )
        return "\n".join(lines)

    def _explain_agents(self) -> str:
        return (
            "After you submit the Predict form, four agents work in order:\n\n"
            "1. **Perception** — reads the customer profile (age, balance, activity, etc.)\n"
            "2. **Prediction** — runs the Deep Neural Network model for churn probability\n"
            "3. **Offer** — selects coupons and offers for that risk level\n"
            "4. **Retention** — summarizes what action to take (email, call, loyalty touch)\n\n"
            "You see the result, offers, and plan on the same page."
        )

    def _explain_model(self, q: str) -> str:
        if "smote" in q:
            return (
                "**SMOTE** balances the training data by creating synthetic churn examples, "
                "so the model does not ignore customers who actually churn. "
                "It is used in the training notebook before the train/test split."
            )
        return (
            "The app uses a **Deep Neural Network** classifier saved as `churn_model.cbm`.\n\n"
            "Training (in the notebook) uses SMOTE, engineered features "
            "(age×balance, tenure×products, and others), and reaches about **91% accuracy** "
            "and **0.91 ROC AUC** on the test set.\n\n"
            "The live app labels churn when probability is **above 0.5**."
        )

    def _explain_churn(self, q: str) -> str:
        if "threshold" in q or "0.5" in q:
            return (
                "**Churn** means the customer is likely to leave the bank. "
                "The model outputs a probability from 0 to 1. "
                "Above **0.5** → label **Churn**; at or below → **No Churn**. "
                "Training also tuned a **0.52** threshold on the test set for best metrics."
            )
        return (
            "**Customer churn** is when someone closes their account or stops using your services.\n\n"
            "On **Predict**, fill in the form and click *Predict Churn*. "
            "You get the probability, the Churn / No Churn label, and tailored coupons and offers "
            "to help retain that customer."
        )

    def _explain_firebase(self) -> str:
        return (
            "Predictions can be saved to **Firebase Realtime Database** under `predictions`, "
            "including the customer data, churn result, coupons, offers, and agent plan. "
            "This uses the service account JSON file in the project folder."
        )

    def _explain_project(self) -> str:
        return (
            "**ChurnAI Agent** is a Flask app for bank customer churn:\n\n"
            "• **Home** — overview and model metrics\n"
            "• **About** — how the model was built\n"
            "• **Predict** — run churn scoring and see retention offers\n"
            "• **Chat** — ask questions (like you're doing now)\n\n"
            "Built with Python, Flask, Deep Neural Network, and NumPy."
        )

    def _fallback(self) -> str:
        return (
            "I'm not fully sure what you meant, but I can help if you ask about:\n"
            "a specific code (e.g. **CARD-SIGNUP**), risk tiers, how prediction works, "
            "or coupons vs offers.\n\n"
            "Try pasting an offer name from your Predict result — I'll explain it clearly."
        )
