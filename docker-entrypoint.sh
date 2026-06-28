#!/usr/bin/env sh
set -e

# On first start (fresh container), build the schema, load the real UCI data
# and train the risk model. Requires CREDDY_DB_* to point at a reachable Postgres.
if [ ! -f models/risk_model.joblib ]; then
  echo "Bootstrapping: schema + UCI data + model training ..."
  creddy setup
fi

exec creddy serve --http --host 0.0.0.0 --port "${PORT:-7860}"
