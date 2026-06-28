"""SQL safety guard.

The MCP server lets an LLM generate SQL. We must guarantee that only
**read-only, single-statement SELECT** queries ever reach the database, and that
every query is capped to a maximum number of rows.

Strategy (defense-in-depth, this is layer 1; the read-only DB session is layer 2):

1. Parse the SQL with ``sqlglot``. Reject anything that does not parse.
2. Require exactly one statement (blocks ``SELECT 1; DROP TABLE ...`` stacking).
3. Require the top-level node to be a SELECT / UNION / CTE.
4. Walk the whole syntax tree and reject if any write/DDL/command node appears.
5. Enforce a row limit (capping a user-supplied limit if it is too large).
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

DIALECT = "postgres"

# Node class names (sqlglot) that must never appear anywhere in the query.
# ``Command`` is sqlglot's catch-all for statements it does not model
# (e.g. COPY, VACUUM, SET) - rejecting it closes a large hole.
_FORBIDDEN_NODE_NAMES = {
    "Insert", "Update", "Delete", "Merge",
    "Drop", "Create", "Alter", "AlterTable", "AlterColumn",
    "TruncateTable", "Truncate",
    "Grant", "Revoke",
    "Command", "Set", "SetItem",
    "Copy", "Call", "Use", "Pragma", "Attach", "Detach",
    "Transaction", "Commit", "Rollback",
}

_ALLOWED_TOP_LEVEL = (exp.Select, exp.Union, exp.Subquery, exp.With)


class SqlGuardError(ValueError):
    """Raised when a query is rejected by the guard."""


def _existing_limit_value(statement: exp.Expression) -> int | None:
    """Return the integer value of a top-level LIMIT, if present and parseable."""
    if isinstance(statement, exp.Select):
        limit = statement.args.get("limit")
        if limit is not None:
            try:
                return int(limit.expression.name)
            except (AttributeError, ValueError, TypeError):
                return None
    return None


def validate_and_prepare(sql: str, row_limit: int = 1000) -> str:
    """Validate ``sql`` and return a normalized, row-capped SELECT string.

    Raises ``SqlGuardError`` if the query is not a safe read-only SELECT.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SqlGuardError("Empty query.")

    try:
        statements = [s for s in sqlglot.parse(cleaned, read=DIALECT) if s is not None]
    except Exception as exc:  # noqa: BLE001 - sqlglot raises various parse errors
        raise SqlGuardError(f"Could not parse SQL: {exc}") from exc

    if len(statements) != 1:
        raise SqlGuardError("Only a single SELECT statement is allowed.")

    statement = statements[0]
    if not isinstance(statement, _ALLOWED_TOP_LEVEL):
        raise SqlGuardError(
            f"Only read-only SELECT queries are allowed (got {type(statement).__name__})."
        )

    for item in statement.walk():
        node = item[0] if isinstance(item, tuple) else item
        name = type(node).__name__
        if name in _FORBIDDEN_NODE_NAMES:
            raise SqlGuardError(f"Disallowed operation detected: {name}.")

    existing_limit = _existing_limit_value(statement)
    if existing_limit is not None and existing_limit <= row_limit:
        final = statement
    else:
        try:
            final = statement.limit(row_limit)
        except Exception:  # noqa: BLE001 - fall back to a wrapping subquery
            final = exp.select("*").from_(statement.subquery(alias="_q")).limit(row_limit)

    return final.sql(dialect=DIALECT)
