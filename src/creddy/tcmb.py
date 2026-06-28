"""Live client for the TCMB EVDS API (Türkiye Cumhuriyet Merkez Bankası -
Electronic Data Delivery System).

This pulls REAL, current Turkish macro/financial series (FX rates, consumer loan
rates, card spending, NPL ratios, ...). A free API key is required; get one at
https://evds3.tcmb.gov.tr and set CREDDY_TCMB_API_KEY in your .env.

Browse series codes at https://evds3.tcmb.gov.tr/tumSeriler
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from .config import Settings


class TcmbError(RuntimeError):
    """Raised for configuration or API errors talking to EVDS."""


def _split_codes(series: str) -> list[str]:
    """Accept series separated by ',' or '-' and normalize to a list."""
    return [c.strip() for c in series.replace(",", "-").split("-") if c.strip()]


def build_url(base_url: str, codes: list[str], start: str, end: str) -> str:
    """Build the EVDS REST request URL (pure function, easy to test)."""
    joined = "-".join(codes)
    base = base_url.rstrip("/")
    return f"{base}/series={joined}&startDate={start}&endDate={end}&type=json"


def fetch_series(
    settings: Settings,
    series: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[list[dict], list[str]]:
    """Fetch one or more EVDS series. Returns (items, codes).

    Dates are ``dd-MM-yyyy``; defaults to the last 12 months.
    """
    if not settings.tcmb_api_key:
        raise TcmbError(
            "TCMB API key missing. Get a free key at https://evds3.tcmb.gov.tr "
            "and set CREDDY_TCMB_API_KEY in your .env file."
        )

    codes = _split_codes(series)
    if not codes:
        raise TcmbError("No EVDS series code provided.")

    end = end_date or date.today().strftime("%d-%m-%Y")
    start = start_date or (date.today() - timedelta(days=365)).strftime("%d-%m-%Y")
    url = build_url(settings.tcmb_base_url, codes, start, end)

    try:
        response = httpx.get(url, headers={"key": settings.tcmb_api_key}, timeout=30.0)
    except httpx.HTTPError as exc:
        raise TcmbError(f"EVDS request failed: {exc}") from exc

    if 300 <= response.status_code < 400:
        raise TcmbError(
            f"EVDS endpoint redirected (HTTP {response.status_code} -> "
            f"{response.headers.get('location', '')}). The public REST endpoint has "
            "likely moved; set CREDDY_TCMB_BASE_URL, or use the tcmb_indicators tool."
        )
    if response.status_code >= 400:
        raise TcmbError(
            f"EVDS returned HTTP {response.status_code}. Check the series code(s), "
            "your API key, and CREDDY_TCMB_BASE_URL."
        )
    if "json" not in response.headers.get("content-type", "").lower():
        raise TcmbError(
            "EVDS did not return JSON (got an HTML page). The public REST endpoint "
            "appears unavailable; use the tcmb_indicators tool or set CREDDY_TCMB_BASE_URL."
        )

    return response.json().get("items", []), codes


def fetch_indicators(settings: Settings) -> list[dict]:
    """Fetch live headline Turkish indicators (USD, EUR, gold, rates, ...).

    Uses the EVDS3 site's public "most-followed series" feed. No API key required.
    """
    url = f"{settings.tcmb_site_url.rstrip('/')}/igmevdsms-dis/sk-seriler"
    headers = {"key": settings.tcmb_api_key} if settings.tcmb_api_key else {}
    try:
        response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise TcmbError(f"TCMB indicators request failed: {exc}") from exc


def search_series(
    settings: Settings,
    query: str,
    *,
    max_datagroups: int = 6,
    max_series: int = 40,
) -> list[dict]:
    """Search the EVDS catalog (categories -> datagroups -> series) by name.

    Uses the key-authenticated EVDS3 endpoints and returns matching series with
    their EVDS code, name and frequency. Requires an API key.
    """
    if not settings.tcmb_api_key:
        raise TcmbError(
            "TCMB API key missing. Get a free key at https://evds3.tcmb.gov.tr "
            "and set CREDDY_TCMB_API_KEY in your .env file."
        )
    if not query.strip():
        raise TcmbError("Empty search query.")

    api = f"{settings.tcmb_site_url.rstrip('/')}/igmevdsms-dis"
    headers = {"key": settings.tcmb_api_key}
    tokens = [t for t in query.lower().split() if t]

    try:
        categories = httpx.get(
            f"{api}/categories/withDatagroups/type=json", headers=headers, timeout=30.0
        ).json()
    except httpx.HTTPError as exc:
        raise TcmbError(f"TCMB catalog request failed: {exc}") from exc

    matched: list[dict] = []
    for category in categories:
        topic = category.get("TOPIC_TITLE_TR") or ""
        topic_en = category.get("TOPIC_TITLE_ENG") or ""
        for group in category.get("DATAGROUPS") or []:
            gtype = group.get("DATAGROUP_TYPE") or ""
            gtype_en = group.get("DATAGROUP_TYPE_ENG") or ""
            haystack = f"{topic} {topic_en} {gtype} {gtype_en}".lower()
            if all(token in haystack for token in tokens):
                matched.append(
                    {
                        "code": group.get("DATAGROUP_CODE"),
                        "name": f"{topic} - {gtype}".strip(" -"),
                        "frequency": group.get("FREQUENCY_STR", ""),
                    }
                )

    results: list[dict] = []
    for group in matched[:max_datagroups]:
        try:
            series = httpx.get(
                f"{api}/serieList/fe/type=json&code={group['code']}", headers=headers, timeout=30.0
            ).json()
        except httpx.HTTPError:
            continue
        for item in series:
            results.append(
                {
                    "seri_kodu": item.get("SERIE_CODE"),
                    "seri_adi": " ".join((item.get("SERIE_NAME") or "").split()),
                    "frekans": item.get("FREQUENCY_STR", group["frequency"]),
                    "veri_grubu": group["name"],
                }
            )
            if len(results) >= max_series:
                return results
    return results
