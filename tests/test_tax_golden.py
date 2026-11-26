"""Golden test: finlog must reproduce the figures of the filed 2025 tax return sheet.

The inputs are real personal data, so they live under user_data/ (ignored by git):

    user_data/tax_golden/2025/
        vests.csv, dividend.csv, sales.csv  # broker export layout
        fx_rates.csv                        # MURC rates used by the sheet
        carryover_2024.json                 # end-of-2024 holdings and average cost
        expected.json                       # figures from the [確定申告] 2025 sheet
"""

import datetime
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from finlog.io.csv_reader import read_csv_lines
from finlog.models.tax import CarryoverState
from finlog.parsers.tax import DividendParser, SalesParser, VestsParser
from finlog.tax.engine import GSUTaxEngine
from finlog.tax.fx_provider import FXProvider

GOLDEN_2025 = Path("user_data/tax_golden/2025")

pytestmark = pytest.mark.skipif(not GOLDEN_2025.exists(), reason=f"{GOLDEN_2025} is not available")


def _no_network(url: str) -> bytes:
    raise AssertionError(f"golden test must not fetch {url}")


@pytest.fixture
def result_2025(tmp_path):
    fx_cache = tmp_path / "fx_cache.csv"
    shutil.copy(GOLDEN_2025 / "fx_rates.csv", fx_cache)
    carryover = CarryoverState.from_dict(json.loads((GOLDEN_2025 / "carryover_2024.json").read_text()))
    engine = GSUTaxEngine(fx_provider=FXProvider(cache_path=fx_cache, http_get=_no_network))
    return engine.process(
        vests=VestsParser().parse(read_csv_lines(str(GOLDEN_2025 / "vests.csv"))),
        dividends=DividendParser().parse(read_csv_lines(str(GOLDEN_2025 / "dividend.csv"))),
        sales=SalesParser().parse(read_csv_lines(str(GOLDEN_2025 / "sales.csv"))),
        carryover=carryover,
        tax_year=2025,
    )


@pytest.fixture
def expected_2025():
    return json.loads((GOLDEN_2025 / "expected.json").read_text(encoding="utf-8"))


def test_2025_vest_income_matches_sheet(result_2025, expected_2025):
    assert result_2025.total_vest_income_jpy == Decimal(expected_2025["total_vest_income_jpy"])
    assert sum(r.shares for r in result_2025.vest_rows) == Decimal(expected_2025["vested_shares"])


def test_2025_dividend_and_foreign_tax_match_sheet(result_2025, expected_2025):
    assert result_2025.total_cash_dividend_jpy == Decimal(expected_2025["total_cash_dividend_jpy"])
    assert result_2025.total_foreign_tax_withheld_jpy == Decimal(expected_2025["total_foreign_tax_withheld_jpy"])


def test_2025_reinvested_shares_match_sheet(result_2025, expected_2025):
    reinvested = sum(r.shares_change for r in result_2025.timeline_rows if r.event_type == "REINVESTMENT")
    assert reinvested == Decimal(expected_2025["reinvested_shares"])


def test_2025_year_end_carryover_matches_sheet(result_2025, expected_2025):
    carryover = result_2025.year_end_carryover
    assert carryover.year == 2025
    assert carryover.shares == Decimal(expected_2025["year_end_shares"])
    assert carryover.average_cost_per_share.quantize(Decimal("0.0001")) == Decimal(
        expected_2025["year_end_average_cost_per_share"]
    )


def test_2025_uses_only_murc_rates(result_2025):
    assert result_2025.used_fx_rates
    assert all(r.source.startswith("MURC") for r in result_2025.used_fx_rates)
    assert result_2025.used_fx_rates[0].date == datetime.date(2025, 1, 25)
