"""Unit tests for the SQL safety guard. These do not require a database."""

import pytest

from creddy.sql_guard import SqlGuardError, validate_and_prepare


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from orders",
        "SELECT count(*) FROM payments WHERE status = 'paid'",
        "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
        "SELECT * FROM orders UNION SELECT * FROM orders",
        "SELECT category, sum(order_amount) FROM orders o JOIN merchants m USING (merchant_id) GROUP BY category",
    ],
)
def test_allowed_queries_get_a_limit(sql):
    out = validate_and_prepare(sql, row_limit=50)
    assert "limit" in out.lower()


def test_user_limit_above_cap_is_reduced():
    out = validate_and_prepare("SELECT * FROM orders LIMIT 100000", row_limit=1000)
    assert "1000" in out
    assert "100000" not in out


def test_user_limit_below_cap_is_preserved():
    out = validate_and_prepare("SELECT * FROM orders LIMIT 10", row_limit=1000)
    assert "10" in out


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders VALUES (1)",
        "UPDATE orders SET status = 'x'",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "TRUNCATE orders",
        "ALTER TABLE orders ADD COLUMN x int",
        "CREATE TABLE t (id int)",
        "SELECT 1; DROP TABLE orders",
        "GRANT ALL ON orders TO public",
        "COPY orders FROM '/etc/passwd'",
        "",
    ],
)
def test_rejected_queries(sql):
    with pytest.raises(SqlGuardError):
        validate_and_prepare(sql)
