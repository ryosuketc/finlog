import csv
import io
import json
import datetime
from decimal import Decimal
import click
from pathlib import Path
from typing import Dict, List, Any, Optional

from finlog.io.csv_reader import read_csv_lines
from finlog.io.sheets_writer import SheetsWriter
from finlog.parsers.zaim import ZaimParser
from finlog.parsers.amex import AmexParser
from finlog.parsers.visa import VisaParser
from finlog.parsers.tax import VestsParser, DividendParser, SalesParser
from finlog.models.tax import CarryoverState
from finlog.tax.fx_provider import FXProvider
from finlog.tax.engine import GSUTaxEngine, GSUTaxCalculationResult
from finlog.matching.engine import ReconciliationEngine
from finlog.config import get_drive_folder_id


@click.group()
def main():
    """finlog: Finance log management, credit card reconciliation, and tax calculation CLI tool."""
    pass


@main.command()
@click.option("--log", type=click.Path(exists=True), required=True, help="Path to personal finance log CSV (e.g. Zaim export)")
@click.option("--log-type", type=str, default="zaim", help="Type of finance log (default: zaim)")
@click.option("--card", type=click.Path(exists=True), required=True, help="Path to credit card statement CSV")
@click.option("--card-type", type=str, required=True, help="Type of credit card statement (visa, amex)")
@click.option("--credentials", "-c", type=click.Path(exists=True), default=None, help="Path to OAuth credentials JSON file")
@click.option("--service-account", type=click.Path(exists=True), default=None, help="Path to Service Account JSON file")
@click.option("--include-all-accounts", is_flag=True, default=False, help="Include all Zaim accounts (including Paid) for matching")
@click.option("--dev", is_flag=True, default=False, help="Use development Google Drive destination folder")
@click.option("--folder-id", type=str, default=None, help="Explicit Google Drive destination folder ID")
def credit(
    log: str,
    log_type: str,
    card: str,
    card_type: str,
    credentials: Optional[str],
    service_account: Optional[str],
    include_all_accounts: bool,
    dev: bool,
    folder_id: Optional[str],
):
    """Reconcile personal finance log against a credit card statement."""
    click.echo(f"Processing finlog credit: log={log} ({log_type}), card={card} ({card_type})")

    # 1. Read CSV lines
    log_lines = read_csv_lines(log)
    card_lines = read_csv_lines(card)

    # Parse raw CSV rows using csv.reader so they are split into individual cell arrays
    raw_card_rows = list(csv.reader(io.StringIO("\n".join(card_lines))))
    raw_zaim_rows = list(csv.reader(io.StringIO("\n".join(log_lines))))

    # 2. Select Parsers
    if log_type.lower() == "zaim":
        log_parser = ZaimParser()
    else:
        raise click.BadParameter(f"Unsupported log type: {log_type}")

    c_type = card_type.lower()
    if c_type in ("visa", "ana_visa"):
        card_parser = VisaParser()
        card_label = "VISA"
    elif c_type in ("amex", "amex_proper"):
        card_parser = AmexParser()
        card_label = "AMEX"
    else:
        raise click.BadParameter(f"Unsupported card type: {card_type}")

    # 3. Parse transactions
    zaim_txs = log_parser.parse(log_lines)
    card_txs = card_parser.parse(card_lines)

    click.echo(f"Parsed {len(zaim_txs)} Zaim transactions and {len(card_txs)} {card_label} card transactions.")

    # 4. Reconcile transactions
    engine = ReconciliationEngine(unpaid_only=not include_all_accounts)
    if card_txs:
        with click.progressbar(
            length=len(card_txs),
            label="Reconciling transactions",
        ) as bar:
            def _cb(current, total):
                bar.update(1)

            result = engine.reconcile(
                card_transactions=card_txs,
                zaim_transactions=zaim_txs,
                progress_callback=_cb,
            )
    else:
        result = engine.reconcile(card_transactions=card_txs, zaim_transactions=zaim_txs)

    # 5. Determine Date Range & Creation Timestamp (JST) for Auto-Title
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_str = datetime.datetime.now(jst).strftime("%Y%m%d_%H%M%S")
    if card_txs:
        card_dates = sorted([c.date for c in card_txs])
        date_str = f"{card_dates[0].strftime('%Y-%m')} ~ {card_dates[-1].strftime('%Y-%m')}"
    else:
        date_str = "No Transactions"

    title = f"finlog credit: Zaim vs {card_label} ({date_str}) ({now_str})"

    # 6. Construct 4 Sheet Tables
    sheets_data: Dict[str, List[List[Any]]] = {
        "Raw Credit Card Log": sort_raw_card_rows(raw_card_rows),
        "Raw Zaim Log": raw_zaim_rows,
        "Zaim View": _format_zaim_view_table(result.zaim_view_entries),
        "Credit View": _format_credit_view_table(result.credit_view_entries),
    }

    # 7. Write output
    target_folder_id = get_drive_folder_id(dev=dev, override_id=folder_id)
    writer = SheetsWriter()
    output_msg = writer.write_output(
        title,
        sheets_data,
        service_account_path=service_account,
        credentials_path=credentials,
        folder_id=target_folder_id,
    )

    click.echo(f"\nReconciliation Summary for {card_label}:")
    click.echo(f"  - Matched Transactions: {len(result.matched_pairs)}")
    click.echo(f"  - Unmatched Card Charges: {len(result.unmatched_card_txs)}")
    click.echo(f"\n{output_msg}")


@main.command()
@click.option("--vests", type=click.Path(exists=True), required=True, help="Path to Vests CSV file")
@click.option("--dividend", type=click.Path(exists=True), required=True, help="Path to Dividend CSV file")
@click.option("--sales", type=click.Path(exists=True), required=True, help="Path to Sales CSV file")
@click.option("--carryover", type=click.Path(exists=True), default=None, help="Path to previous year carryover JSON file")
@click.option("--output-carryover", type=click.Path(), default=None, help="Path to save current year carryover JSON file")
@click.option("--use-cache/--no-cache", default=True, help="Use local FX rate CSV cache (default: True)")
@click.option("--credentials", "-c", type=click.Path(exists=True), default=None, help="Path to OAuth credentials JSON file")
@click.option("--service-account", type=click.Path(exists=True), default=None, help="Path to Service Account JSON file")
@click.option("--dev", is_flag=True, default=False, help="Use development Google Drive destination folder")
@click.option("--folder-id", type=str, default=None, help="Explicit Google Drive destination folder ID")
def gsu(
    vests: str,
    dividend: str,
    sales: str,
    carryover: Optional[str],
    output_carryover: Optional[str],
    use_cache: bool,
    credentials: Optional[str],
    service_account: Optional[str],
    dev: bool,
    folder_id: Optional[str],
):
    """Calculate Japanese tax return (確定申告) tables for Google Stock Units (GSU)."""
    click.echo(f"Processing finlog gsu: vests={vests}, dividend={dividend}, sales={sales}")

    # 1. Read raw CSV lines
    vests_lines = read_csv_lines(vests)
    dividend_lines = read_csv_lines(dividend)
    sales_lines = read_csv_lines(sales)

    raw_vests_rows = list(csv.reader(io.StringIO("\n".join(vests_lines))))
    raw_dividend_rows = list(csv.reader(io.StringIO("\n".join(dividend_lines))))
    raw_sales_rows = list(csv.reader(io.StringIO("\n".join(sales_lines))))

    # 2. Parse records
    vest_records = VestsParser().parse(vests_lines)
    dividend_records = DividendParser().parse(dividend_lines)
    sale_records = SalesParser().parse(sales_lines)

    click.echo(
        f"Parsed {len(vest_records)} Vest records, {len(dividend_records)} Dividend records, and {len(sale_records)} Sale records."
    )

    # 3. Load carryover if provided
    initial_carryover: Optional[CarryoverState] = None
    if carryover:
        with open(carryover, "r", encoding="utf-8") as f:
            carry_dict = json.load(f)
            initial_carryover = CarryoverState.from_dict(carry_dict)
            click.echo(f"Loaded initial carryover: {initial_carryover.shares} shares @ ¥{initial_carryover.average_cost_per_share}/share")

    # 4. Run Tax Calculation Engine
    fx_provider = FXProvider(use_cache=use_cache)
    engine = GSUTaxEngine(fx_provider=fx_provider)
    result = engine.process(
        vests=vest_records,
        dividends=dividend_records,
        sales=sale_records,
        carryover=initial_carryover,
    )

    # 5. Save output carryover JSON
    output_carryover_path = Path(output_carryover) if output_carryover else Path(f"user_data/carryover_{result.tax_year}.json")
    output_carryover_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_carryover_path, "w", encoding="utf-8") as f:
        json.dump(result.year_end_carryover.to_dict(), f, indent=2)
    click.echo(f"Year-end carryover state saved to: {output_carryover_path.resolve()}")

    # 6. Format Spreadsheet Sheets
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_str = datetime.datetime.now(jst).strftime("%Y%m%d_%H%M%S")
    title = f"finlog gsu tax report: {result.tax_year} ({now_str})"

    sheets_data: Dict[str, List[List[Any]]] = {
        "Vests": _format_vests_table(result),
        "Dividend": _format_dividend_table(result),
        "Sales & Capital Gains": _format_sales_table(result),
        "Acquisition Cost Audit": _format_acquisition_audit_table(result),
        "FX Rates Audit": _format_fx_table(result),
        "Raw Vests": raw_vests_rows,
        "Raw Dividend": raw_dividend_rows,
        "Raw Sales": raw_sales_rows,
    }

    # 7. Write output
    target_folder_id = get_drive_folder_id(dev=dev, override_id=folder_id)
    writer = SheetsWriter()
    output_msg = writer.write_output(
        title,
        sheets_data,
        service_account_path=service_account,
        credentials_path=credentials,
        folder_id=target_folder_id,
    )

    click.echo("\nTax Calculation Summary:")
    click.echo(f"  - Tax Year: {result.tax_year}")
    click.echo(f"  - Total Vest Salary Income (給与所得): ¥{result.total_vest_income_jpy:,}")
    click.echo(f"  - Total Cash Dividend Income (配当所得): ¥{result.total_cash_dividend_jpy:,}")
    click.echo(f"  - Total Foreign Tax Withheld (外国税控除): ¥{result.total_foreign_tax_withheld_jpy:,}")
    click.echo(f"  - Total Capital Gains (譲渡所得): ¥{result.total_capital_gains_jpy:,}")
    click.echo(f"  - Year-End Remaining Shares: {result.year_end_carryover.shares} (Avg Cost: ¥{result.year_end_carryover.average_cost_per_share}/share)")
    click.echo(f"\n{output_msg}")


def sort_raw_card_rows(rows: List[List[Any]]) -> List[List[Any]]:
    """Sort raw credit card CSV rows by transaction date in ASC order.

    Preserves top non-transaction header/metadata rows and bottom summary footer rows.
    """
    if not rows:
        return []

    def _parse_row_date(row: List[Any]) -> Optional[datetime.date]:
        if not row or not row[0]:
            return None
        s = str(row[0]).strip().replace("/", "-")
        parts = s.split("-")
        if len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 4:
            try:
                return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                return None
        return None

    first_date_idx = None
    last_date_idx = None

    for idx, row in enumerate(rows):
        dt = _parse_row_date(row)
        if dt is not None:
            if first_date_idx is None:
                first_date_idx = idx
            last_date_idx = idx

    if first_date_idx is None:
        return list(rows)

    header_rows = rows[:first_date_idx]
    footer_rows = rows[last_date_idx + 1 :]
    data_rows = rows[first_date_idx : last_date_idx + 1]

    sorted_data_rows = sorted(
        data_rows,
        key=lambda r: _parse_row_date(r) or datetime.date.min,
    )

    return header_rows + sorted_data_rows + footer_rows


def _format_zaim_view_table(entries: List[Dict[str, Any]]) -> List[List[Any]]:
    header = [
        "transaction_id",
        "date",
        "type",
        "account",
        "amount",
        "category",
        "subcategory",
        "item",
        "payee_payer",
        "tag_mod",
        "note",
        "match_status",
        "matched_transaction_id",
    ]
    rows = [header]
    for d in entries:
        rows.append([d.get(col, "") for col in header])
    return rows


def _format_credit_view_table(entries: List[Dict[str, Any]]) -> List[List[Any]]:
    header = [
        "transaction_id",
        "card_company",
        "date",
        "amount",
        "payee_merchant",
        "cardholder",
        "card_number_suffix",
        "note",
        "match_status",
        "matched_transaction_id",
    ]
    rows = [header]
    for d in entries:
        rows.append([d.get(col, "") for col in header])
    return rows


def _format_vests_table(res: GSUTaxCalculationResult) -> List[List[Any]]:
    header = ["award_date", "vesting_date", "shares", "fmv_usd", "ttm", "income_jpy"]
    rows = [header]
    total_shares = Decimal("0")
    for r in res.vest_rows:
        total_shares += r.shares
        rows.append([
            r.award_date.isoformat(),
            r.vesting_date.isoformat(),
            float(r.shares),
            float(r.fmv_usd),
            float(r.ttm),
            int(r.income_jpy),
        ])
    rows.append(["TOTAL SALARY INCOME", "", float(total_shares), "", "", int(res.total_vest_income_jpy)])
    return rows


def _format_dividend_table(res: GSUTaxCalculationResult) -> List[List[Any]]:
    header = ["entry_date", "activity", "amount_usd", "ttm", "amount_jpy"]
    rows = [header]
    for r in res.dividend_rows:
        rows.append([
            r.entry_date.isoformat(),
            r.activity,
            float(r.amount_usd),
            float(r.ttm),
            int(r.amount_jpy),
        ])
    rows.append([])
    rows.append(["TOTAL CASH DIVIDEND INCOME (配当所得)", "", "", "", int(res.total_cash_dividend_jpy)])
    rows.append(["TOTAL FOREIGN TAX WITHHELD (外国税控除)", "", "", "", int(res.total_foreign_tax_withheld_jpy)])
    return rows


def _format_sales_table(res: GSUTaxCalculationResult) -> List[List[Any]]:
    header = [
        "execution_date",
        "quantity_sold",
        "sale_price_usd",
        "ttb",
        "gross_proceeds_jpy",
        "avg_acq_cost_jpy_per_share",
        "total_acq_cost_jpy",
        "fee_usd",
        "fee_jpy",
        "capital_gain_jpy",
        "remaining_shares",
    ]
    rows = [header]
    for r in res.sale_rows:
        rows.append([
            r.execution_date.isoformat(),
            float(r.quantity_sold),
            float(r.sale_price_usd),
            float(r.ttb),
            int(r.gross_proceeds_jpy),
            float(r.avg_acq_cost_jpy_per_share),
            int(r.total_acq_cost_jpy),
            float(r.fee_usd),
            int(r.fee_jpy),
            int(r.capital_gain_jpy),
            float(r.remaining_shares),
        ])
    rows.append(["TOTAL CAPITAL GAINS (譲渡所得)", "", "", "", "", "", "", "", "", int(res.total_capital_gains_jpy), ""])
    return rows


def _format_acquisition_audit_table(res: GSUTaxCalculationResult) -> List[List[Any]]:
    header = [
        "date",
        "event_type",
        "description",
        "shares_change",
        "price_usd",
        "tts_ttb",
        "event_val_jpy",
        "fee_usd",
        "fee_jpy",
        "running_total_shares",
        "running_total_cost_jpy",
        "running_avg_cost_jpy_per_share",
    ]
    rows = [header]
    for r in res.timeline_rows:
        rows.append([
            r.date.isoformat(),
            r.event_type,
            r.description,
            float(r.shares_change),
            float(r.price_usd),
            float(r.fx_rate),
            int(r.event_val_jpy),
            float(r.fee_usd),
            int(r.fee_jpy),
            float(r.running_shares),
            int(r.running_total_cost_jpy),
            float(r.running_avg_cost_jpy),
        ])
    return rows


def _format_fx_table(res: GSUTaxCalculationResult) -> List[List[Any]]:
    header = ["date", "ttm", "tts", "ttb", "source"]
    rows = [header]
    for r in res.used_fx_rates:
        rows.append([
            r.date.isoformat(),
            float(r.ttm),
            float(r.tts),
            float(r.ttb),
            r.source,
        ])
    return rows


if __name__ == "__main__":
    main()
