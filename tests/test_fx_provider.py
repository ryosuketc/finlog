import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from finlog.tax.fx_provider import FXProvider, FXRateUnavailableError, parse_murc_usd

TESTDATA = Path(__file__).parent / "testdata"
MURC_PAGE_2025_01_24 = (TESTDATA / "murc_2025-01-24.html").read_bytes()
MURC_URL_2025_01_24 = "https://www.murc-kawasesouba.jp/fx/past_3month_result.php?y=2025&m=1&d=24"
NO_RATE_PAGE = b"<html><body>no data</body></html>"


class FakeHttp:
    """Serves canned responses by URL and records every requested URL."""

    def __init__(self, pages=None):
        self.pages = pages or {}
        self.requested = []

    def __call__(self, url: str) -> bytes:
        self.requested.append(url)
        if url in self.pages:
            return self.pages[url]
        raise OSError(f"unreachable: {url}")


def test_parse_murc_usd_reads_usd_row():
    assert parse_murc_usd(MURC_PAGE_2025_01_24) == (Decimal("157.33"), Decimal("155.33"), Decimal("156.33"))


def test_parse_murc_usd_returns_none_without_usd_row():
    assert parse_murc_usd(NO_RATE_PAGE) is None


def test_get_rate_uses_murc_page_for_business_day():
    http = FakeHttp({MURC_URL_2025_01_24: MURC_PAGE_2025_01_24})
    provider = FXProvider(use_cache=False, http_get=http)

    rate = provider.get_rate(datetime.date(2025, 1, 24))

    assert (rate.tts, rate.ttb, rate.ttm) == (Decimal("157.33"), Decimal("155.33"), Decimal("156.33"))
    assert rate.date == datetime.date(2025, 1, 24)
    assert rate.source == "MURC"


def test_get_rate_falls_back_to_preceding_business_day_on_weekend():
    saturday_url = "https://www.murc-kawasesouba.jp/fx/past_3month_result.php?y=2025&m=1&d=25"
    http = FakeHttp({saturday_url: NO_RATE_PAGE, MURC_URL_2025_01_24: MURC_PAGE_2025_01_24})
    provider = FXProvider(use_cache=False, http_get=http)

    rate = provider.get_rate(datetime.date(2025, 1, 25))

    assert rate.date == datetime.date(2025, 1, 25)
    assert rate.ttm == Decimal("156.33")
    assert rate.source == "MURC (2025-01-24)"


def test_get_rate_falls_back_to_frankfurter_when_murc_is_unavailable():
    frankfurter_url = "https://api.frankfurter.app/2025-01-24?from=USD&to=JPY"
    http = FakeHttp({frankfurter_url: b'{"rates": {"JPY": 156.1}}'})
    provider = FXProvider(use_cache=False, http_get=http)

    rate = provider.get_rate(datetime.date(2025, 1, 24))

    assert (rate.tts, rate.ttb, rate.ttm) == (Decimal("157.1"), Decimal("155.1"), Decimal("156.1"))
    assert rate.source == "Frankfurter API"


def test_get_rate_raises_when_no_source_has_a_rate():
    provider = FXProvider(use_cache=False, http_get=FakeHttp())

    with pytest.raises(FXRateUnavailableError, match="2025-01-24"):
        provider.get_rate(datetime.date(2025, 1, 24))


def test_get_rate_uses_cached_murc_rate_without_http(tmp_path):
    cache = tmp_path / "fx_cache.csv"
    cache.write_text("date,ttm,tts,ttb,source\n2025-01-24,156.33,157.33,155.33,MURC\n", encoding="utf-8")
    http = FakeHttp()
    provider = FXProvider(cache_path=cache, http_get=http)

    rate = provider.get_rate(datetime.date(2025, 1, 24))

    assert rate.ttm == Decimal("156.33")
    assert http.requested == []


def test_get_rate_refetches_cached_non_murc_rate_from_murc(tmp_path):
    cache = tmp_path / "fx_cache.csv"
    cache.write_text("date,ttm,tts,ttb,source\n2025-01-24,156.1,157.1,155.1,Frankfurter API\n", encoding="utf-8")
    http = FakeHttp({MURC_URL_2025_01_24: MURC_PAGE_2025_01_24})
    provider = FXProvider(cache_path=cache, http_get=http)

    rate = provider.get_rate(datetime.date(2025, 1, 24))

    assert rate.ttm == Decimal("156.33")
    assert rate.source == "MURC"
    assert "2025-01-24,156.33,157.33,155.33,MURC" in cache.read_text(encoding="utf-8")
