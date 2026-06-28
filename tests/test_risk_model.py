"""Unit tests for the risk model pipeline. No database required."""

import pandas as pd

from creddy.risk_model import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_pipeline,
)


def _tiny_df(n: int = 40) -> pd.DataFrame:
    import random

    random.seed(0)
    rows = []
    for _ in range(n):
        rows.append(
            {
                "credit_limit": random.uniform(1000, 100000),
                "age": random.randint(20, 70),
                "pay_sep": random.choice([-1, 0, 1, 2]),
                "pay_aug": random.choice([-1, 0, 1, 2]),
                "pay_jul": random.choice([-1, 0, 1, 2]),
                "bill_sep": random.uniform(0, 50000),
                "pay_amt_sep": random.uniform(0, 10000),
                "sex": random.choice(["erkek", "kadın"]),
                "education": random.choice(["lise", "üniversite", "yüksek lisans"]),
                "marriage": random.choice(["evli", "bekar"]),
            }
        )
    return pd.DataFrame(rows)


def test_feature_lists_are_disjoint():
    assert set(NUMERIC_FEATURES).isdisjoint(CATEGORICAL_FEATURES)
    assert "pay_sep" in NUMERIC_FEATURES
    assert "education" in CATEGORICAL_FEATURES


def test_pipeline_trains_and_predicts_probabilities():
    df = _tiny_df()
    y = [i % 2 for i in range(len(df))]  # both classes guaranteed
    model = build_pipeline()
    model.fit(df[ALL_FEATURES], y)
    proba = model.predict_proba(df[ALL_FEATURES])[:, 1]
    assert len(proba) == len(df)
    assert all(0.0 <= float(p) <= 1.0 for p in proba)
