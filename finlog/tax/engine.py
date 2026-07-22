import datetime
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any

from finlog.models.tax import (
    CarryoverState,
    VestRecord,
    DividendRecord,
    SaleRecord,
    FXRateRecord,
)
from finlog.tax.fx_provider import FXProvider


def round_jpy(val: Decimal) -> Decimal:
    """Round Decimal currency value to integer JPY using ROUND_HALF_UP."""
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def round_2dec(val: Decimal) -> Decimal:
    """Round Decimal to 2 decimal places."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class VestResultRow:
    award_date: datetime.date
    vesting_date: datetime.date
    shares: Decimal
    fmv_usd: Decimal
    ttm: Decimal
    income_jpy: Decimal


@dataclass
class DividendResultRow:
    entry_date: datetime.date
    activity: str
    amount_usd: Decimal
    ttm: Decimal
    amount_jpy: Decimal


@dataclass
class SaleResultRow:
    execution_date: datetime.date
    quantity_sold: Decimal
    sale_price_usd: Decimal
    ttb: Decimal
    gross_proceeds_jpy: Decimal
    avg_acq_cost_jpy_per_share: Decimal
    total_acq_cost_jpy: Decimal
    fee_usd: Decimal
    fee_jpy: Decimal
    capital_gain_jpy: Decimal
    remaining_shares: Decimal


@dataclass
class AcquisitionTimelineRow:
    """Detailed audit row tracking stock inventory changes event-by-event."""
    date: datetime.date
    event_type: str
    description: str
    shares_change: Decimal
    price_usd: Decimal
    fx_rate: Decimal
    event_val_jpy: Decimal
    fee_usd: Decimal
    fee_jpy: Decimal
    running_shares: Decimal
    running_total_cost_jpy: Decimal
    running_avg_cost_jpy: Decimal


@dataclass
class GSUTaxCalculationResult:
    tax_year: int
    vest_rows: List[VestResultRow]
    total_vest_income_jpy: Decimal

    dividend_rows: List[DividendResultRow]
    total_cash_dividend_jpy: Decimal
    total_foreign_tax_withheld_jpy: Decimal

    sale_rows: List[SaleResultRow]
    total_capital_gains_jpy: Decimal

    used_fx_rates: List[FXRateRecord]
    timeline_rows: List[AcquisitionTimelineRow]
    year_end_carryover: CarryoverState


class GSUTaxEngine:
    """Tax Calculation & Total Average Cost Engine for Google Stock Units (GSU)."""

    def __init__(self, fx_provider: Optional[FXProvider] = None):
        self.fx_provider = fx_provider or FXProvider()

    def process(
        self,
        vests: List[VestRecord],
        dividends: List[DividendRecord],
        sales: List[SaleRecord],
        carryover: Optional[CarryoverState] = None,
        tax_year: Optional[int] = None,
    ) -> GSUTaxCalculationResult:
        # Determine tax year from data if not explicitly provided
        all_dates = (
            [v.vesting_date for v in vests]
            + [d.entry_date for d in dividends]
            + [s.execution_date for s in sales]
        )
        if not tax_year:
            tax_year = all_dates[0].year if all_dates else datetime.date.today().year

        used_fx_map: Dict[datetime.date, FXRateRecord] = {}

        # 1. Process Vests (給与所得)
        vest_rows: List[VestResultRow] = []
        total_vest_income_jpy = Decimal("0")
        sorted_vests = sorted(vests, key=lambda v: v.vesting_date)

        for v in sorted_vests:
            fx = self.fx_provider.get_rate(v.vesting_date)
            used_fx_map[v.vesting_date] = fx
            income_jpy = round_jpy(v.shares * v.fmv_usd * fx.ttm)
            total_vest_income_jpy += income_jpy
            vest_rows.append(
                VestResultRow(
                    award_date=v.award_date,
                    vesting_date=v.vesting_date,
                    shares=v.shares,
                    fmv_usd=v.fmv_usd,
                    ttm=fx.ttm,
                    income_jpy=income_jpy,
                )
            )

        # 2. Process Dividends (配当所得 & 外国税控除)
        dividend_rows: List[DividendResultRow] = []
        total_cash_dividend_jpy = Decimal("0")
        total_foreign_tax_withheld_jpy = Decimal("0")
        sorted_divs = sorted(dividends, key=lambda d: d.entry_date)

        for d in sorted_divs:
            if d.activity == "You bought":
                continue  # Handled in capital gains stock acquisition

            fx = self.fx_provider.get_rate(d.entry_date)
            used_fx_map[d.entry_date] = fx

            if d.activity == "Dividend (Cash)":
                jpy_val = round_jpy(d.cash_usd * fx.ttm)
                total_cash_dividend_jpy += jpy_val
                dividend_rows.append(
                    DividendResultRow(
                        entry_date=d.entry_date,
                        activity=d.activity,
                        amount_usd=d.cash_usd,
                        ttm=fx.ttm,
                        amount_jpy=jpy_val,
                    )
                )
            elif d.activity == "IRS Nonresident Alien Withholding":
                abs_cash = abs(d.cash_usd)
                jpy_val = round_jpy(abs_cash * fx.ttm)
                total_foreign_tax_withheld_jpy += jpy_val
                dividend_rows.append(
                    DividendResultRow(
                        entry_date=d.entry_date,
                        activity=d.activity,
                        amount_usd=d.cash_usd,
                        ttm=fx.ttm,
                        amount_jpy=jpy_val,
                    )
                )

        # 3. Process Capital Gains (総平均法 - Total Average Cost Method) & Audit Timeline
        timeline_rows: List[AcquisitionTimelineRow] = []
        current_shares = Decimal("0")
        current_avg_cost_jpy = Decimal("0")

        # Initial carryover row
        if carryover and carryover.shares > Decimal("0"):
            current_shares = carryover.shares
            current_avg_cost_jpy = carryover.average_cost_per_share
            initial_cost_jpy = current_shares * current_avg_cost_jpy
            start_date = datetime.date(tax_year - 1, 12, 31)
            timeline_rows.append(
                AcquisitionTimelineRow(
                    date=start_date,
                    event_type="CARRYOVER",
                    description=f"Initial carryover from {carryover.year}",
                    shares_change=current_shares,
                    price_usd=Decimal("0"),
                    fx_rate=Decimal("0"),
                    event_val_jpy=round_jpy(initial_cost_jpy),
                    fee_usd=Decimal("0"),
                    fee_jpy=Decimal("0"),
                    running_shares=current_shares,
                    running_total_cost_jpy=round_jpy(initial_cost_jpy),
                    running_avg_cost_jpy=round_2dec(current_avg_cost_jpy),
                )
            )

        # Build chronological event list for inventory tracking
        # Event tuple: (date, type_str, shares, price_usd, original_obj)
        events: List[Tuple[datetime.date, str, Decimal, Decimal, Any]] = []

        for v in vests:
            events.append((v.vesting_date, "VEST", v.shares, v.fmv_usd, v))

        for d in dividends:
            if d.activity == "You bought" and d.shares > Decimal("0"):
                events.append((d.entry_date, "REINVESTMENT", d.shares, d.share_price_usd, d))

        for s in sales:
            events.append((s.execution_date, "SALE", s.quantity, s.price_usd, s))

        # Sort events chronologically. Acquisitions before sales on same date.
        type_order = {"VEST": 1, "REINVESTMENT": 2, "SALE": 3}
        events.sort(key=lambda e: (e[0], type_order.get(e[1], 9)))

        sale_rows: List[SaleResultRow] = []
        total_capital_gains_jpy = Decimal("0")

        for date, event_type, shares, price_usd, orig in events:
            fx = self.fx_provider.get_rate(date)
            used_fx_map[date] = fx

            if event_type == "VEST":
                event_cost_jpy = round_jpy(shares * price_usd * fx.tts)
                prev_total_cost = current_shares * current_avg_cost_jpy
                new_shares = current_shares + shares
                new_total_cost = prev_total_cost + event_cost_jpy

                current_shares = new_shares
                if current_shares > Decimal("0"):
                    current_avg_cost_jpy = new_total_cost / current_shares
                else:
                    current_avg_cost_jpy = price_usd * fx.tts

                timeline_rows.append(
                    AcquisitionTimelineRow(
                        date=date,
                        event_type="VEST",
                        description=f"GSU Vest ({shares} shares)",
                        shares_change=shares,
                        price_usd=price_usd,
                        fx_rate=fx.tts,
                        event_val_jpy=event_cost_jpy,
                        fee_usd=Decimal("0"),
                        fee_jpy=Decimal("0"),
                        running_shares=current_shares,
                        running_total_cost_jpy=round_jpy(current_shares * current_avg_cost_jpy),
                        running_avg_cost_jpy=round_2dec(current_avg_cost_jpy),
                    )
                )

            elif event_type == "REINVESTMENT":
                event_cost_jpy = round_jpy(shares * price_usd * fx.tts)
                prev_total_cost = current_shares * current_avg_cost_jpy
                new_shares = current_shares + shares
                new_total_cost = prev_total_cost + event_cost_jpy

                current_shares = new_shares
                if current_shares > Decimal("0"):
                    current_avg_cost_jpy = new_total_cost / current_shares
                else:
                    current_avg_cost_jpy = price_usd * fx.tts

                timeline_rows.append(
                    AcquisitionTimelineRow(
                        date=date,
                        event_type="REINVESTMENT",
                        description=f"Dividend Reinvestment ({shares} shares)",
                        shares_change=shares,
                        price_usd=price_usd,
                        fx_rate=fx.tts,
                        event_val_jpy=event_cost_jpy,
                        fee_usd=Decimal("0"),
                        fee_jpy=Decimal("0"),
                        running_shares=current_shares,
                        running_total_cost_jpy=round_jpy(current_shares * current_avg_cost_jpy),
                        running_avg_cost_jpy=round_2dec(current_avg_cost_jpy),
                    )
                )

            elif event_type == "SALE":
                gross_proceeds = round_jpy(shares * price_usd * fx.ttb)
                fee_usd = getattr(orig, "fee_usd", Decimal("0"))
                fee_jpy = round_jpy(fee_usd * fx.ttb) if fee_usd > Decimal("0") else Decimal("0")
                acq_cost_sold = round_jpy(shares * current_avg_cost_jpy)
                capital_gain = gross_proceeds - acq_cost_sold - fee_jpy

                current_shares = current_shares - shares
                total_capital_gains_jpy += capital_gain

                sale_rows.append(
                    SaleResultRow(
                        execution_date=date,
                        quantity_sold=shares,
                        sale_price_usd=price_usd,
                        ttb=fx.ttb,
                        gross_proceeds_jpy=gross_proceeds,
                        avg_acq_cost_jpy_per_share=round_2dec(current_avg_cost_jpy),
                        total_acq_cost_jpy=acq_cost_sold,
                        fee_usd=fee_usd,
                        fee_jpy=fee_jpy,
                        capital_gain_jpy=capital_gain,
                        remaining_shares=current_shares,
                    )
                )

                timeline_rows.append(
                    AcquisitionTimelineRow(
                        date=date,
                        event_type="SALE",
                        description=f"Stock Sale ({shares} shares)",
                        shares_change=-shares,
                        price_usd=price_usd,
                        fx_rate=fx.ttb,
                        event_val_jpy=gross_proceeds,
                        fee_usd=fee_usd,
                        fee_jpy=fee_jpy,
                        running_shares=current_shares,
                        running_total_cost_jpy=round_jpy(current_shares * current_avg_cost_jpy),
                        running_avg_cost_jpy=round_2dec(current_avg_cost_jpy),
                    )
                )

        year_end_carryover = CarryoverState(
            year=tax_year,
            shares=current_shares,
            average_cost_per_share=round_2dec(current_avg_cost_jpy),
        )

        used_fx_records = sorted(used_fx_map.values(), key=lambda r: r.date)

        return GSUTaxCalculationResult(
            tax_year=tax_year,
            vest_rows=vest_rows,
            total_vest_income_jpy=total_vest_income_jpy,
            dividend_rows=dividend_rows,
            total_cash_dividend_jpy=total_cash_dividend_jpy,
            total_foreign_tax_withheld_jpy=total_foreign_tax_withheld_jpy,
            sale_rows=sale_rows,
            total_capital_gains_jpy=total_capital_gains_jpy,
            used_fx_rates=used_fx_records,
            timeline_rows=timeline_rows,
            year_end_carryover=year_end_carryover,
        )
