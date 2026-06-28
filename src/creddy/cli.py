"""Command-line interface: ``creddy init-db | load-data | serve``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .data_loader import load
from .db import run_sql_script
from .server import build_server

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "sql" / "schema.sql"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="creddy",
        description="Creddy - natural language to safe SQL over real credit data.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create the database schema (drops existing tables).")

    load_parser = sub.add_parser(
        "load-data", help="Fetch the real UCI credit-default dataset and load it."
    )
    load_parser.add_argument(
        "--limit", type=int, default=None, help="Load only the first N rows (for quick tests)."
    )

    sub.add_parser("train-model", help="Train the default-risk model on the loaded data.")

    sub.add_parser("setup", help="One-shot: init-db + load-data + train-model.")

    serve_parser = sub.add_parser("serve", help="Run the MCP server (stdio by default).")
    serve_parser.add_argument(
        "--http", action="store_true", help="Serve over Streamable HTTP instead of stdio."
    )
    serve_parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP bind host (use 0.0.0.0 in containers)."
    )
    serve_parser.add_argument("--port", type=int, default=8000, help="HTTP port.")

    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "init-db":
        run_sql_script(settings, SCHEMA_PATH)
        print(f"Schema created from {SCHEMA_PATH}")
    elif args.command == "load-data":
        load(settings, limit=args.limit)
    elif args.command == "train-model":
        from .risk_model import train

        train(settings)
    elif args.command == "setup":
        run_sql_script(settings, SCHEMA_PATH)
        print(f"Schema created from {SCHEMA_PATH}")
        load(settings)
        from .risk_model import train

        train(settings)
    elif args.command == "serve":
        if args.http:
            server = build_server(settings, host=args.host, port=args.port, stateless_http=True)
            print(f"Serving MCP over Streamable HTTP at http://{args.host}:{args.port}/mcp")
            server.run(transport="streamable-http")
        else:
            build_server(settings).run()


if __name__ == "__main__":
    main()
