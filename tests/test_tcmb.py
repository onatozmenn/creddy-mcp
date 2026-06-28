"""Unit tests for the TCMB EVDS client. No network access required."""

import pytest

from creddy.config import Settings
from creddy.tcmb import TcmbError, _split_codes, build_url, fetch_series


def test_split_codes_handles_dash_and_comma():
    assert _split_codes("TP.DK.USD.A-TP.DK.EUR.A") == ["TP.DK.USD.A", "TP.DK.EUR.A"]
    assert _split_codes("a, b , c") == ["a", "b", "c"]


def test_build_url():
    url = build_url(
        "https://evds3.tcmb.gov.tr/igmevdsms-dis/",
        ["TP.DK.USD.A", "TP.DK.EUR.A"],
        "01-01-2024",
        "01-01-2025",
    )
    assert url == (
        "https://evds3.tcmb.gov.tr/igmevdsms-dis/series=TP.DK.USD.A-TP.DK.EUR.A"
        "&startDate=01-01-2024&endDate=01-01-2025&type=json"
    )


def test_missing_api_key_raises():
    settings = Settings(tcmb_api_key="")
    with pytest.raises(TcmbError):
        fetch_series(settings, "TP.DK.USD.A")
