"""The MCP server: exposes safe, read-only analytics tools over the creddy data.

Built with FastMCP. Designed to be driven by Claude (or any MCP client): the
client supplies natural language, the model writes SQL, and these tools execute
it safely and return results.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .db import connect
from .risk_model import RiskModelError, load_metrics
from .risk_model import predict as run_prediction
from .sql_guard import SqlGuardError, validate_and_prepare
from .tcmb import TcmbError, fetch_indicators, fetch_series, search_series

EXAMPLE_QUESTIONS = [
    "Eğitim düzeyine göre temerrüt oranı nedir?",
    "Yaş gruplarına göre temerrüt oranı nasıl değişiyor?",
    "Kredi limiti yüksek müşteriler daha az mı temerrüde düşüyor?",
    "Son ay ödemesini geciktirenlerde temerrüt oranı nedir?",
    "(Canlı TCMB) Güncel dolar, euro ve altın fiyatları nedir?",
    "(TCMB) 'kredi kartı' harcama serilerini bul.",
    "Bu profilin temerrüt riski nedir: 40 yaş, limit 50000, eylülde 2 ay gecikme?",
    "Risk modelinin başarısı (AUC) nedir?",
]


def _fmt(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(columns: list[str], rows: list[dict], max_rows: int = 100) -> str:
    if not rows:
        return "(no rows)"
    shown = rows[:max_rows]
    head = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(_fmt(r.get(c)) for c in columns) + " |" for r in shown]
    table = "\n".join([head, sep, *body])
    note = "" if len(rows) <= max_rows else f"\n\n(showing first {max_rows} of {len(rows)} rows)"
    return table + note


def _render(sql: str, columns: list[str], rows: list[dict]) -> str:
    header = f"-- executed SQL --\n{sql}\n\n{len(rows)} row(s) returned.\n"
    return header + "\n" + _markdown_table(columns, rows)


def build_server(
    settings: Settings | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    stateless_http: bool = False,
) -> FastMCP:
    settings = settings or Settings()
    mcp = FastMCP("creddy", host=host, port=port, stateless_http=stateless_http)

    @mcp.tool()
    def list_tables() -> str:
        """List the available tables in the creddy analytics database."""
        sql = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        with connect(settings) as conn:
            rows = conn.execute(sql).fetchall()
        return "\n".join(r["table_name"] for r in rows) or "(no tables found)"

    @mcp.tool()
    def describe_schema() -> str:
        """Return every table's columns and types.

        Call this first to ground SQL generation in the real schema before
        writing a query for ``run_query``.
        """
        sql = (
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        )
        with connect(settings) as conn:
            rows = conn.execute(sql).fetchall()

        if not rows:
            return "(schema is empty - run `creddy init-db` and `creddy seed` first)"

        lines: list[str] = []
        current = None
        for r in rows:
            if r["table_name"] != current:
                current = r["table_name"]
                lines.append(f"\n{current}:")
            nullable = "" if r["is_nullable"] == "YES" else " NOT NULL"
            lines.append(f"  - {r['column_name']}: {r['data_type']}{nullable}")
        return "\n".join(lines).strip()

    @mcp.tool()
    def run_query(sql: str) -> str:
        """Run a READ-ONLY SQL SELECT query and return the result as a table.

        Queries run against `credit_clients` (real UCI data, 30k clients).
        Only a single SELECT statement is allowed; writes, DDL and multiple
        statements are rejected and results are capped. Monetary columns are in
        New Taiwan Dollars (NT$); `defaulted` is a boolean target label.
        """
        try:
            safe_sql = validate_and_prepare(sql, row_limit=settings.query_row_limit)
        except SqlGuardError as exc:
            return f"Query rejected by safety guard: {exc}"

        with connect(settings, read_only=True) as conn:
            cur = conn.execute(safe_sql)
            rows = cur.fetchall()
            columns = [d.name for d in cur.description] if cur.description else []
        return _render(safe_sql, columns, rows)

    @mcp.tool()
    def tcmb_indicators(contains: str = "") -> str:
        """LIVE headline Turkish indicators from TCMB (USD, EUR, gold, policy rate, ...).

        Optionally filter by a substring of the indicator name, e.g. 'Dolar',
        'Euro', 'Altın'. Returns the current value, date and EVDS series code.
        Works without an API key.
        """
        try:
            items = fetch_indicators(settings)
        except TcmbError as exc:
            return str(exc)
        rows = []
        for it in items:
            name = it.get("gorunurAdi", "")
            if contains and contains.lower() not in name.lower():
                continue
            rows.append(
                {
                    "gosterge": name,
                    "deger": it.get("deger"),
                    "tarih": it.get("tarih"),
                    "seri_kodu": it.get("seriKodu"),
                }
            )
        if not rows:
            return f"No indicators matched '{contains}'."
        return _markdown_table(["gosterge", "deger", "tarih", "seri_kodu"], rows)

    @mcp.tool()
    def tcmb_series(series: str, start_date: str = "", end_date: str = "") -> str:
        """Fetch a specific time series from TCMB's public REST web service.

        `series`: one or more EVDS codes separated by '-' or ',', e.g.
        'TP.DK.USD.A.YTL'. `start_date`/`end_date`: 'dd-MM-yyyy' (default: last year).
        Requires CREDDY_TCMB_API_KEY (free at evds3.tcmb.gov.tr). Targets the EVDS3
        public REST endpoint; override CREDDY_TCMB_BASE_URL only if it changes again.
        """
        try:
            items, codes = fetch_series(settings, series, start_date or None, end_date or None)
        except TcmbError as exc:
            return str(exc)
        if not items:
            return f"No data returned for: {', '.join(codes)}"
        columns = list(items[0].keys())
        header = f"TCMB EVDS - {', '.join(codes)}  ({len(items)} observations)\n\n"
        return header + _markdown_table(columns, items)

    @mcp.tool()
    def tcmb_search(query: str) -> str:
        """Search TCMB's EVDS catalog for series by topic/name (key-authenticated).

        Returns matching EVDS series with their code, name and frequency. Example
        queries: 'döviz kuru', 'kredi kartı', 'enflasyon', 'altın', 'konut'. Use a
        returned code with `tcmb_series` once TCMB's public REST endpoint is available.
        Requires CREDDY_TCMB_API_KEY.
        """
        try:
            rows = search_series(settings, query)
        except TcmbError as exc:
            return str(exc)
        if not rows:
            return f"No series matched '{query}'."
        return _markdown_table(["seri_kodu", "seri_adi", "frekans", "veri_grubu"], rows)

    @mcp.tool()
    def predict_default(
        credit_limit: float,
        age: int,
        pay_sep: int = 0,
        pay_aug: int = 0,
        pay_jul: int = 0,
        sex: str = "kadın",
        education: str = "üniversite",
        marriage: str = "bekar",
        bill_sep: float = 0.0,
        pay_amt_sep: float = 0.0,
    ) -> str:
        """Predict a client's probability of default and explain the top drivers.

        Trained on the real credit_clients data. `credit_limit`, `bill_sep`,
        `pay_amt_sep` are in NT$. `pay_sep`/`pay_aug`/`pay_jul` are the repayment
        status for Sep/Aug/Jul (-1/0 = paid duly, >=1 = months of delay). `sex`
        (erkek/kadın), `education` (lise/üniversite/yüksek lisans/diğer), `marriage`
        (evli/bekar/diğer). Run `creddy train-model` first.
        """
        features = {
            "credit_limit": credit_limit, "age": age,
            "pay_sep": pay_sep, "pay_aug": pay_aug, "pay_jul": pay_jul,
            "bill_sep": bill_sep, "pay_amt_sep": pay_amt_sep,
            "sex": sex, "education": education, "marriage": marriage,
        }
        try:
            result = run_prediction(features)
        except RiskModelError as exc:
            return str(exc)
        lines = [
            f"Temerrüt olasılığı: %{result['probability'] * 100:.1f} — {result['band']} risk",
            "",
            "En etkili faktörler:",
        ]
        for factor in result["factors"]:
            arrow = "↑" if factor["effect"] > 0 else "↓"
            lines.append(f"  {arrow} {factor['feature']}: {factor['effect']:+.3f}")
        return "\n".join(lines)

    @mcp.tool()
    def model_metrics() -> str:
        """Return the trained risk model's evaluation metrics and key drivers."""
        try:
            m = load_metrics()
        except RiskModelError as exc:
            return str(exc)
        lines = [
            f"Model: {m['model']}",
            f"Eğitim/Test: {m['n_train']} / {m['n_test']} müşteri",
            f"Veri temerrüt oranı: %{m['default_rate'] * 100:.1f}",
            f"Karar eşiği (Youden J): {m['threshold']:.3f}",
            "",
            f"AUC: {m['auc']:.3f}  Doğruluk: {m['accuracy']:.3f}  "
            f"Precision: {m['precision']:.3f}  Recall: {m['recall']:.3f}  "
            f"F1: {m['f1']:.3f}  KS: {m['ks']:.3f}",
            "",
            "En belirleyici özellikler (ağırlık):",
        ]
        for factor in m["top_features"]:
            arrow = "↑" if factor["weight"] > 0 else "↓"
            lines.append(f"  {arrow} {factor['feature']}: {factor['weight']:+.3f}")
        return "\n".join(lines)

    @mcp.tool()
    def example_questions() -> str:
        """Return example analytics questions this server can answer."""
        return "\n".join(f"- {q}" for q in EXAMPLE_QUESTIONS)

    return mcp
