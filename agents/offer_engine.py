"""Maps churn probability and customer profile to retention coupons and offers."""

RISK_TIERS = (
    ("low", 0.0, 0.30),
    ("moderate", 0.30, 0.50),
    ("high", 0.50, 0.70),
    ("critical", 0.70, 1.01),
)


def _risk_tier(probability: float) -> str:
    for name, low, high in RISK_TIERS:
        if low <= probability < high:
            return name
    return "critical"


def _base_offers(tier: str, probability: float) -> list[dict]:
    catalog = {
        "low": [
            {
                "type": "coupon",
                "code": "LOYAL10",
                "title": "10% Loyalty Cashback",
                "description": "Thank-you cashback on the next statement for staying with us.",
                "value": "10%",
            },
            {
                "type": "offer",
                "code": "PRIORITY-SUPPORT",
                "title": "Priority Support Line",
                "description": "Dedicated queue for account questions and quick resolutions.",
                "value": "Free upgrade",
            },
        ],
        "moderate": [
            {
                "type": "coupon",
                "code": "STAY15",
                "title": "15% Fee Waiver Coupon",
                "description": "Waive service fees on one product for the next billing cycle.",
                "value": "15%",
            },
            {
                "type": "offer",
                "code": "CHECKIN-CALL",
                "title": "Relationship Manager Check-in",
                "description": "Personal call to review goals and optimize your product mix.",
                "value": "Scheduled within 7 days",
            },
        ],
        "high": [
            {
                "type": "coupon",
                "code": "SAVE25",
                "title": "25% Retention Discount",
                "description": "Discount on annual maintenance or subscription fees.",
                "value": "25%",
            },
            {
                "type": "offer",
                "code": "FLEX-PLAN",
                "title": "Flexible Payment Plan",
                "description": "Restructure dues with lower installments for 3 months.",
                "value": "0% setup fee",
            },
            {
                "type": "coupon",
                "code": "BONUS50",
                "title": "$50 Account Credit",
                "description": "One-time credit applied when the customer remains active 60 days.",
                "value": "$50",
            },
        ],
        "critical": [
            {
                "type": "coupon",
                "code": "VIP40",
                "title": "40% VIP Retention Package",
                "description": "Maximum discount on fees plus waived penalties for one cycle.",
                "value": "40%",
            },
            {
                "type": "offer",
                "code": "EXEC-ESCALATION",
                "title": "Executive Retention Specialist",
                "description": "Same-day outreach from a senior retention agent.",
                "value": "Within 24 hours",
            },
            {
                "type": "coupon",
                "code": "CREDIT100",
                "title": "$100 Loyalty Credit",
                "description": "Immediate account credit if the customer accepts the retention bundle.",
                "value": "$100",
            },
            {
                "type": "offer",
                "code": "CUSTOM-BUNDLE",
                "title": "Custom Product Bundle",
                "description": "Tailored multi-product package priced below standalone products.",
                "value": "Personalized quote",
            },
        ],
    }
    offers = list(catalog[tier])
    if probability >= 0.85 and tier == "critical":
        offers.append(
            {
                "type": "offer",
                "code": "LAST-CHANCE",
                "title": "Last-Chance Retention Match",
                "description": "We match a competitor offer up to a capped amount after verification.",
                "value": "Up to $150",
            }
        )
    return offers


def _personalized_offers(customer: dict) -> list[dict]:
    extras = []
    if int(customer["is_active"]) == 0:
        extras.append(
            {
                "type": "coupon",
                "code": "REACTIVATE20",
                "title": "20% Reactivation Bonus",
                "description": "Reward for completing one transaction after re-engagement.",
                "value": "20%",
            }
        )
    if int(customer["has_card"]) == 0:
        extras.append(
            {
                "type": "offer",
                "code": "CARD-SIGNUP",
                "title": "Premium Card Sign-up Offer",
                "description": "No annual fee for the first year plus bonus rewards points.",
                "value": "First year free",
            }
        )
    if int(customer["num_products"]) <= 1:
        extras.append(
            {
                "type": "offer",
                "code": "BUNDLE-PLUS",
                "title": "Multi-Product Bundle Discount",
                "description": "Add a second product at a reduced bundled rate.",
                "value": "30% off add-on",
            }
        )
    if float(customer["balance"]) > 100000:
        extras.append(
            {
                "type": "offer",
                "code": "WEALTH-DESK",
                "title": "Dedicated Wealth Desk Access",
                "description": "Priority advisor for high-balance accounts.",
                "value": "Complimentary quarter",
            }
        )
    if int(customer["tenure"]) >= 5:
        extras.append(
            {
                "type": "coupon",
                "code": "TENURE-LOYAL",
                "title": "Long-Tenure Appreciation",
                "description": "Extra loyalty points for customers with 5+ years tenure.",
                "value": "500 bonus points",
            }
        )
    return extras


def build_retention_offers(customer: dict, probability: float, label: str) -> dict:
    tier = _risk_tier(probability)
    offers = _base_offers(tier, probability)
    offers.extend(_personalized_offers(customer))

    seen = set()
    unique_offers = []
    for offer in offers:
        key = offer["code"]
        if key not in seen:
            seen.add(key)
            unique_offers.append(offer)

    churn_pct = round(probability * 100, 1)
    if label == "Churn":
        urgency = "immediate" if probability >= 0.7 else "high" if probability >= 0.5 else "standard"
    else:
        urgency = "proactive" if probability >= 0.35 else "low"

    return {
        "risk_tier": tier,
        "churn_probability_pct": churn_pct,
        "urgency": urgency,
        "coupons": [o for o in unique_offers if o["type"] == "coupon"],
        "offers": [o for o in unique_offers if o["type"] == "offer"],
        "all_items": unique_offers,
    }
