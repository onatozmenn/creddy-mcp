"""A real, interpretable default-risk model trained on the credit_clients data.

We use a logistic-regression pipeline (standardize numerics + one-hot encode
categoricals). Logistic regression is chosen deliberately: it gives clean,
*signed per-feature contributions* for every prediction, which matters for a
credit-risk model (explainable / adverse-action friendly) and avoids heavy
dependencies like SHAP.

Artifacts (model + metrics) are written to ``models/`` and reused by the MCP
tools so predictions are instant and reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Settings
from .db import connect

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models"
MODEL_PATH = MODELS_DIR / "risk_model.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"

NUMERIC_FEATURES = ["credit_limit", "age", "pay_sep", "pay_aug", "pay_jul", "bill_sep", "pay_amt_sep"]
CATEGORICAL_FEATURES = ["sex", "education", "marriage"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Risk bands are derived from the model's operating threshold (Youden's J),
# stored with the model after training.
_MODEL = None


class RiskModelError(RuntimeError):
    """Raised when the model is missing or cannot be used."""


def build_pipeline():
    """Create the (untrained) model pipeline. Exposed for testing."""
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(
        [
            ("pre", pre),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def _load_dataframe(settings: Settings) -> pd.DataFrame:
    sql = f"SELECT {', '.join(ALL_FEATURES)}, defaulted FROM credit_clients"
    with connect(settings) as conn:
        rows = conn.execute(sql).fetchall()
    if not rows:
        raise RiskModelError("No data in credit_clients. Run `creddy init-db` and `creddy load-data` first.")
    df = pd.DataFrame(rows)
    for col in NUMERIC_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["defaulted"] = df["defaulted"].astype(int)
    return df


def _ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(y_score)
    y = np.asarray(y_true)[order]
    pos = np.cumsum(y) / max(1, int(y.sum()))
    neg = np.cumsum(1 - y) / max(1, int((1 - y).sum()))
    return float(np.max(np.abs(pos - neg)))


def _clean_name(name: str) -> str:
    return name.replace("num__", "").replace("cat__", "")


def train(settings: Settings | None = None, *, test_size: float = 0.2, random_state: int = 42) -> dict:
    """Train the model, evaluate on a held-out split, and persist artifacts."""
    import joblib
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
        roc_curve,
    )
    from sklearn.model_selection import train_test_split

    settings = settings or Settings()
    df = _load_dataframe(settings)
    X = df[ALL_FEATURES]
    y = df["defaulted"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = build_pipeline()
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    fpr, tpr, thresholds = roc_curve(y_test, proba)
    threshold = float(thresholds[int(np.argmax(tpr - fpr))])
    pred = (proba >= threshold).astype(int)

    names = [_clean_name(n) for n in model.named_steps["pre"].get_feature_names_out()]
    coefs = model.named_steps["clf"].coef_[0]
    top_features = sorted(
        ({"feature": n, "weight": float(c)} for n, c in zip(names, coefs)),
        key=lambda d: abs(d["weight"]),
        reverse=True,
    )[:10]

    metrics = {
        "model": "LogisticRegression (interpretable linear model)",
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "default_rate": float(y.mean()),
        "threshold": threshold,
        "auc": float(roc_auc_score(y_test, proba)),
        "accuracy": float(accuracy_score(y_test, pred)),
        "precision": float(precision_score(y_test, pred, zero_division=0)),
        "recall": float(recall_score(y_test, pred, zero_division=0)),
        "f1": float(f1_score(y_test, pred, zero_division=0)),
        "ks": _ks_statistic(y_test.to_numpy(), proba),
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
        "top_features": top_features,
    }

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "threshold": threshold}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(
        f"Trained on {metrics['n_train']} / tested on {metrics['n_test']} clients.\n"
        f"AUC={metrics['auc']:.3f}  accuracy={metrics['accuracy']:.3f}  "
        f"precision={metrics['precision']:.3f}  recall={metrics['recall']:.3f}  "
        f"F1={metrics['f1']:.3f}  KS={metrics['ks']:.3f}\n"
        f"Saved model -> {MODEL_PATH}"
    )
    return metrics


def load_model():
    global _MODEL
    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise RiskModelError("Model not trained yet. Run: creddy train-model")
        import joblib

        _MODEL = joblib.load(MODEL_PATH)
    return _MODEL


def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        raise RiskModelError("No metrics found. Run: creddy train-model")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def _band(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "YÜKSEK"
    if probability >= threshold * 0.5:
        return "ORTA"
    return "DÜŞÜK"


def predict(features: dict) -> dict:
    """Predict default probability for one client and explain the top drivers."""
    bundle = load_model()
    model = bundle["model"]
    threshold = bundle["threshold"]
    row = {f: features.get(f) for f in ALL_FEATURES}
    X = pd.DataFrame([row])
    for col in NUMERIC_FEATURES:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    probability = float(model.predict_proba(X)[0, 1])

    pre = model.named_steps["pre"]
    clf = model.named_steps["clf"]
    transformed = np.asarray(pre.transform(X))[0]
    names = [_clean_name(n) for n in pre.get_feature_names_out()]
    contributions = transformed * clf.coef_[0]
    order = np.argsort(np.abs(contributions))[::-1][:5]
    factors = [{"feature": names[i], "effect": float(contributions[i])} for i in order]

    return {"probability": probability, "band": _band(probability, threshold), "factors": factors}
