"""
Train the Deep Neural Network churn model.

Run from the project root:
    python training/train_dnn.py

The script uses the real Bank Churn_Modelling.csv in data/ and saves:
- models/dnn_churn_model.pt
- models/dnn_scaler.joblib
- results/model_metrics.json
- results/confusion_matrix.csv
"""
from pathlib import Path
import json
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
import joblib

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "Churn_Modelling.csv"
MODEL_DIR = ROOT / "models"
RESULT_DIR = ROOT / "results"
MODEL_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

FEATURES = [
    "CreditScore", "Geography", "Gender", "Age", "Tenure", "Balance",
    "NumOfProducts", "HasCrCard", "IsActiveMember", "EstimatedSalary",
    "Age_Balance", "Tenure_Products", "Active_Balance", "Credit_Age",
    "Products_per_Tenure", "ChurnRiskScore",
]

def make_features(df):
    df = df.drop(columns=["RowNumber", "CustomerId", "Surname"]).copy()
    df["Gender"] = df["Gender"].map({"Male": 0, "Female": 1})
    df["Geography"] = df["Geography"].map({"France": 0, "Spain": 1, "Germany": 2})
    df["Age_Balance"] = df["Age"] * df["Balance"]
    df["Tenure_Products"] = df["Tenure"] * df["NumOfProducts"]
    df["Active_Balance"] = df["IsActiveMember"] * df["Balance"]
    df["Credit_Age"] = df["CreditScore"] * df["Age"]
    df["Products_per_Tenure"] = df["NumOfProducts"] / (df["Tenure"] + 1)
    df["ChurnRiskScore"] = (
        df["Age"] * 0.3
        + df["Balance"] * 0.00001
        + (1 - df["IsActiveMember"]) * 2
        + df["NumOfProducts"] * -0.5
    )
    return df[FEATURES].astype(float), df["Exited"].astype(int)

class ChurnDNN(nn.Module):
    def __init__(self, input_dim=16):
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

def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    X, y = make_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X.values, y.values, test_size=0.20, random_state=SEED, stratify=y.values
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=SEED, stratify=y_train
    )

    # SMOTE is applied only to the training partition to avoid test leakage.
    smote = SMOTE(random_state=SEED)
    X_train, y_train = smote.fit_resample(X_train, y_train)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    Xtr = torch.tensor(X_train, dtype=torch.float32)
    ytr = torch.tensor(y_train.reshape(-1, 1), dtype=torch.float32)
    Xv = torch.tensor(X_val, dtype=torch.float32)
    yv = torch.tensor(y_val.reshape(-1, 1), dtype=torch.float32)
    Xt = torch.tensor(X_test, dtype=torch.float32)

    model = ChurnDNN(len(FEATURES))
    optimizer = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)

    pos = max(1, int((y_train == 1).sum()))
    neg = max(1, int((y_train == 0).sum()))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))

    best_state = None
    best_val = float("inf")
    patience = 25
    wait = 0

    for epoch in range(250):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(Xtr), ytr)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(Xv), yv).item()

        if val_loss < best_val - 1e-4:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break

    model.load_state_dict(best_state)
    model.eval()

    with torch.no_grad():
        probabilities = torch.sigmoid(model(Xt)).numpy().ravel()

    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "model": "Deep Neural Network",
        "dataset": "Bank Churn_Modelling.csv",
        "accuracy": round(float(accuracy_score(y_test, predictions)), 6),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 6),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 6),
        "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 6),
        "threshold": 0.50,
        "epochs": epoch + 1,
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
    }

    torch.save({
        "state_dict": model.state_dict(),
        "input_dim": len(FEATURES),
        "architecture": [64, 32, 16],
        "dropout": [0.25, 0.20],
    }, MODEL_DIR / "dnn_churn_model.pt")
    joblib.dump(scaler, MODEL_DIR / "dnn_scaler.joblib")
    (RESULT_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2))
    np.savetxt(
        RESULT_DIR / "confusion_matrix.csv",
        np.asarray(metrics["confusion_matrix"]),
        fmt="%d",
        delimiter=",",
    )

    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
