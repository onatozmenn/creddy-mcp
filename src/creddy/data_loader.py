"""Load the REAL UCI "Default of Credit Card Clients" dataset into Postgres.

The dataset (30,000 real anonymized clients with real repayment history and a
real default label) is fetched live from the UCI Machine Learning Repository via
``ucimlrepo`` - no account or API key required.

Source: https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients
"""

from __future__ import annotations

from .config import Settings
from .db import connect

UCI_DATASET_ID = 350

# Decode the categorical codes to readable Turkish labels so that natural-language
# questions map cleanly onto the data.
SEX = {1: "erkek", 2: "kadın"}
EDUCATION = {1: "yüksek lisans", 2: "üniversite", 3: "lise", 4: "diğer"}
MARRIAGE = {1: "evli", 2: "bekar", 3: "diğer"}

_INSERT = """
INSERT INTO credit_clients (
    client_id, credit_limit, sex, education, marriage, age,
    pay_sep, pay_aug, pay_jul, pay_jun, pay_may, pay_apr,
    bill_sep, bill_aug, bill_jul, bill_jun, bill_may, bill_apr,
    pay_amt_sep, pay_amt_aug, pay_amt_jul, pay_amt_jun, pay_amt_may, pay_amt_apr,
    defaulted
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s
)
"""


def _decode(mapping: dict[int, str], code: int) -> str:
    return mapping.get(int(code), "bilinmiyor")


def load(settings: Settings, *, limit: int | None = None) -> None:
    """Fetch the dataset and load it into the ``credit_clients`` table."""
    try:
        from ucimlrepo import fetch_ucirepo
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "ucimlrepo is required. Install it with: pip install ucimlrepo"
        ) from exc

    print("Fetching real UCI dataset (id=350) ...")
    dataset = fetch_ucirepo(id=UCI_DATASET_ID)
    features = dataset.data.features
    targets = dataset.data.targets.iloc[:, 0]

    if limit is not None:
        features = features.head(limit)
        targets = targets.head(limit)

    rows = []
    # Columns are positional in the source: X1..X23 (see schema.sql for the mapping).
    for client_id, (feat, label) in enumerate(zip(features.itertuples(index=False), targets), start=1):
        v = list(feat)
        rows.append(
            (
                client_id,
                float(v[0]),                       # credit_limit
                _decode(SEX, v[1]),                # sex
                _decode(EDUCATION, v[2]),          # education
                _decode(MARRIAGE, v[3]),           # marriage
                int(v[4]),                         # age
                int(v[5]), int(v[6]), int(v[7]),   # pay_sep..pay_jul
                int(v[8]), int(v[9]), int(v[10]),  # pay_jun..pay_apr
                float(v[11]), float(v[12]), float(v[13]),   # bill_sep..bill_jul
                float(v[14]), float(v[15]), float(v[16]),   # bill_jun..bill_apr
                float(v[17]), float(v[18]), float(v[19]),   # pay_amt_sep..jul
                float(v[20]), float(v[21]), float(v[22]),   # pay_amt_jun..apr
                bool(int(label) == 1),             # defaulted
            )
        )

    with connect(settings, read_only=False) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE credit_clients")
            cur.executemany(_INSERT, rows)

    defaults = sum(1 for r in rows if r[-1])
    print(
        f"Loaded {len(rows)} real clients into credit_clients "
        f"({defaults} defaulted, {defaults / len(rows):.1%})."
    )
