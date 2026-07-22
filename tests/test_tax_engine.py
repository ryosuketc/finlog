import datetime
from decimal import Decimal
from finlog.models.tax import (
    CarryoverState,
    VestRecord,
    DividendRecord,
    SaleRecord,
    FXRateRecord,
)
from finlog.tax.fx_provider import FXProvider
from finlog.tax.engine import GSUTaxEngine


class DummyFXProvider(FXProvider):
    """Mock FXProvider returning 1.0 TTM, 1.0 TTS, 1.0 TTB for testing."""

    def __init__(self, rate_map=None):
        super().__init__(use_cache=False)
        self.rate_map = rate_map or {}

    def get_rate(self, target_date: datetime.date) -> FXRateRecord:
        if target_date in self.rate_map:
            ttm = self.rate_map[target_date]
            return FXRateRecord(
                date=target_date,
                ttm=ttm,
                tts=ttm + Decimal("1.0"),
                ttb=ttm - Decimal("1.0"),
                source="Mock",
            )
        ttm = Decimal("1.0")
        return FXRateRecord(
            date=target_date,
            ttm=ttm,
            tts=ttm,
            ttb=ttm,
            source="Mock",
        )


def test_total_average_cost_worked_example():
    """Verify total average cost method against DRAFT_tax.md worked example."""
    # Event 1: Carryover state (100 shares @ 200 JPY)
    carryover = CarryoverState(
        year=2024,
        shares=Decimal("100"),
        average_cost_per_share=Decimal("200"),
    )

    # Event 2: Vest on 2025-01-01 (100 shares @ 250 JPY)
    vests = [
        VestRecord(
            award_date=datetime.date(2024, 1, 1),
            vesting_date=datetime.date(2025, 1, 1),
            shares=Decimal("100"),
            fmv_usd=Decimal("250"),
        )
    ]

    # Event 3: Dividend Reinvestment on 2025-01-15 (5 shares @ 300 JPY)
    dividends = [
        DividendRecord(
            entry_date=datetime.date(2025, 1, 15),
            activity="You bought",
            cash_usd=Decimal("-1500"),
            shares=Decimal("5"),
            share_price_usd=Decimal("300"),
        )
    ]

    # Event 4: Sale on 2025-02-01 (100 shares @ 400 JPY, $10 fee)
    sales = [
        SaleRecord(
            execution_date=datetime.date(2025, 2, 1),
            price_usd=Decimal("400"),
            quantity=Decimal("100"),
            fee_usd=Decimal("10"),
        )
    ]

    engine = GSUTaxEngine(fx_provider=DummyFXProvider())
    res = engine.process(
        vests=vests,
        dividends=dividends,
        sales=sales,
        carryover=carryover,
        tax_year=2025,
    )

    assert len(res.sale_rows) == 1
    sale_row = res.sale_rows[0]

    # Average cost per share = (100*200 + 100*250 + 5*300) / 205 = 46500 / 205 = 226.83 JPY
    assert sale_row.avg_acq_cost_jpy_per_share == Decimal("226.83")
    assert sale_row.total_acq_cost_jpy == Decimal("22683")
    assert sale_row.gross_proceeds_jpy == Decimal("40000")
    assert sale_row.fee_usd == Decimal("10")
    assert sale_row.fee_jpy == Decimal("10")
    assert sale_row.capital_gain_jpy == Decimal("17307")

    # Remaining state
    assert res.year_end_carryover.shares == Decimal("105")
    assert res.year_end_carryover.average_cost_per_share == Decimal("226.83")

    # Timeline audit rows verification
    assert len(res.timeline_rows) == 4
    assert res.timeline_rows[0].event_type == "CARRYOVER"
    assert res.timeline_rows[0].running_shares == Decimal("100")

    assert res.timeline_rows[1].event_type == "VEST"
    assert res.timeline_rows[1].running_shares == Decimal("200")

    assert res.timeline_rows[2].event_type == "REINVESTMENT"
    assert res.timeline_rows[2].running_shares == Decimal("205")
    assert res.timeline_rows[2].running_avg_cost_jpy == Decimal("226.83")

    assert res.timeline_rows[3].event_type == "SALE"
    assert res.timeline_rows[3].running_shares == Decimal("105")
    assert res.timeline_rows[3].fee_usd == Decimal("10")
    assert res.timeline_rows[3].fee_jpy == Decimal("10")
