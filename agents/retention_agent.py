"""
Agentic retention workflow: perceive → predict → plan offers → act (persist).
"""

from agents.offer_engine import build_retention_offers
from services.churn_predictor import predict_churn


class RetentionAgent:
    """Orchestrates churn prediction and personalized retention actions."""

    def __init__(self, model):
        self.model = model
        self.memory: list[dict] = []

    def perceive(self, customer: dict) -> dict:
        return {
            "credit_score": customer["credit_score"],
            "geography": customer["geography"],
            "gender": customer["gender"],
            "age": customer["age"],
            "tenure": customer["tenure"],
            "balance": customer["balance"],
            "num_products": customer["num_products"],
            "has_card": customer["has_card"],
            "is_active": customer["is_active"],
            "salary": customer["salary"],
        }

    def decide(self, customer: dict) -> dict:
        prediction = predict_churn(self.model, customer)
        retention = build_retention_offers(
            customer, prediction["probability"], prediction["label"]
        )
        plan = self._build_action_plan(prediction, retention)
        return {
            "prediction": prediction,
            "retention": retention,
            "plan": plan,
        }

    def _build_action_plan(self, prediction: dict, retention: dict) -> dict:
        prob = prediction["probability"]
        tier = retention["risk_tier"]
        steps = [
            {
                "agent": "PerceptionAgent",
                "action": "Ingested customer profile and account signals.",
                "status": "done",
            },
            {
                "agent": "PredictionAgent",
                "action": f"DNN churn score: {prob:.2%} ({prediction['label']}).",
                "status": "done",
            },
            {
                "agent": "OfferAgent",
                "action": f"Selected {tier}-risk retention coupons and offers.",
                "status": "done",
            },
            {
                "agent": "RetentionAgent",
                "action": self._primary_action(prediction, retention),
                "status": "recommended",
            },
        ]
        return {
            "goal": "Prevent customer churn",
            "steps": steps,
            "summary": self._summary(prediction, retention),
        }

    def _primary_action(self, prediction: dict, retention: dict) -> str:
        prob = prediction["probability"]
        n_coupons = len(retention["coupons"])
        n_offers = len(retention["offers"])
        if prediction["label"] == "Churn":
            if prob >= 0.7:
                return (
                    f"Deploy critical retention bundle: {n_coupons} coupon(s), "
                    f"{n_offers} offer(s), executive outreach within 24h."
                )
            return (
                f"Send targeted retention package: {n_coupons} coupon(s) and "
                f"{n_offers} offer(s) via email and in-app notification."
            )
        if prob >= 0.35:
            return (
                f"Proactive loyalty touch: share {n_coupons + n_offers} "
                "preventive perk(s) to strengthen engagement."
            )
        return "Maintain relationship with standard loyalty messaging; no urgent intervention."

    def _summary(self, prediction: dict, retention: dict) -> str:
        pct = retention["churn_probability_pct"]
        if prediction["label"] == "Churn":
            return (
                f"High churn risk ({pct}%). Agent recommends immediate coupons and "
                "personalized offers to retain this customer."
            )
        if pct >= 35:
            return (
                f"Model predicts no churn, but elevated risk ({pct}%). "
                "Agent suggests preventive offers to reduce future churn."
            )
        return (
            f"Low churn risk ({pct}%). Light loyalty rewards recommended to "
            "keep satisfaction high."
        )

    def run(self, customer: dict) -> dict:
        snapshot = self.perceive(customer)
        outcome = self.decide(customer)
        trace = {
            "input": snapshot,
            "prediction": outcome["prediction"],
            "retention": outcome["retention"],
            "plan": outcome["plan"],
        }
        self.memory.append(trace)
        return trace

    def to_firebase_payload(self, customer: dict, trace: dict) -> dict:
        """Extends original Firebase record with agent retention data."""
        pred = trace["prediction"]
        ret = trace["retention"]
        return {
            "credit_score": int(customer["credit_score"]),
            "geography": customer["geography"],
            "gender": customer["gender"],
            "age": int(customer["age"]),
            "tenure": int(customer["tenure"]),
            "balance": float(customer["balance"]),
            "num_products": int(customer["num_products"]),
            "has_card": int(customer["has_card"]),
            "is_active": int(customer["is_active"]),
            "salary": float(customer["salary"]),
            "prediction": pred["label"],
            "probability": pred["probability"],
            "agentic": True,
            "risk_tier": ret["risk_tier"],
            "urgency": ret["urgency"],
            "coupons": ret["coupons"],
            "offers": ret["offers"],
            "agent_plan": trace["plan"]["summary"],
            "agent_steps": trace["plan"]["steps"],
        }
