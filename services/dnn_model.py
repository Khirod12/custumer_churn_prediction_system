"""Deep-learning churn model wrapper used by the Flask application."""
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import joblib

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "models" / "dnn_churn_model.pt"
SCALER_PATH = BASE_DIR / "models" / "dnn_scaler.joblib"

GEO_MAP = {"France": 0, "Spain": 1, "Germany": 2}
GENDER_MAP = {"Male": 0, "Female": 1}

FEATURE_NAMES = [
    "CreditScore", "Geography", "Gender", "Age", "Tenure", "Balance",
    "NumOfProducts", "HasCrCard", "IsActiveMember", "EstimatedSalary",
    "Age_Balance", "Tenure_Products", "Active_Balance", "Credit_Age",
    "Products_per_Tenure", "ChurnRiskScore",
]


class ChurnDNN(nn.Module):
    """Feed-forward neural network for binary customer-churn classification."""

    def __init__(self, input_dim: int = 16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(0.25),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(0.20),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.net(x)


def build_features(customer: dict) -> np.ndarray:
    credit_score = int(customer["credit_score"])
    geography = customer["geography"]
    gender = customer["gender"]
    age = int(customer["age"])
    tenure = int(customer["tenure"])
    balance = float(customer["balance"])
    num_products = int(customer["num_products"])
    has_card = int(customer["has_card"])
    is_active = int(customer["is_active"])
    salary = float(customer["salary"])

    geo_val = GEO_MAP[geography]
    gen_val = GENDER_MAP[gender]

    age_balance = age * balance
    tenure_products = tenure * num_products
    active_balance = is_active * balance
    credit_age = credit_score * age
    products_per_tenure = num_products / (tenure + 1)
    churn_risk = (
        age * 0.3
        + balance * 0.00001
        + (1 - is_active) * 2
        + num_products * -0.5
    )

    return np.array([[
        credit_score, geo_val, gen_val, age, tenure, balance, num_products,
        has_card, is_active, salary, age_balance, tenure_products,
        active_balance, credit_age, products_per_tenure, churn_risk
    ]], dtype=np.float32)


class DNNChurnPredictor:
    def __init__(self, model_path=MODEL_PATH, scaler_path=SCALER_PATH):
        self.device = torch.device("cpu")
        self.model = ChurnDNN(input_dim=16).to(self.device)
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()
        self.scaler = joblib.load(scaler_path)

    def predict(self, customer: dict) -> dict:
        raw = build_features(customer)
        scaled = self.scaler.transform(raw)
        tensor = torch.tensor(scaled, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            probability = float(torch.sigmoid(self.model(tensor)).item())

        label = "Churn" if probability >= 0.5 else "No Churn"
        return {
            "label": label,
            "probability": probability,
            "result_text": f"{label} (Probability: {probability:.2f})",
            "model": "Deep Neural Network",
        }


def predict_churn(predictor: DNNChurnPredictor, customer: dict) -> dict:
    return predictor.predict(customer)
