"""医療費控除: turn the reviewed iryohi_raw sheet into 医療費集計フォーム rows, and add review suggestions.

iryohi_raw is the result of the finlog.iryouhi BigQuery query, downloaded as CSV. Rows are numbered like
the sheet: the header is row 1, so the first data row is row 2.
"""

import csv
import datetime
import io
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple, Union

from finlog.io.csv_reader import read_csv_lines
from finlog.parsers.tax import parse_flexible_date

REQUIRED_COLUMNS = (
    "iryouhikoujo_type",
    "year",
    "iryouhikoujo_person",
    "iryouhikoujo_payee",
    "is_type_shinryo",
    "is_type_iyakuhin",
    "is_type_kaigo",
    "is_type_other",
    "iryouhikoujo_amount",
    "iryouhikoujo_refund",
    "iryouhikoujo_date",
    "include",
    "receipt",
    "need_data_fix",
)
CATEGORY_COLUMNS = ("is_type_shinryo", "is_type_iyakuhin", "is_type_kaigo", "is_type_other")
CATEGORY_SELECTED = "該当する"
TRANSPORT_TYPE = "交通費"
TRUE_VALUES = frozenset({"1", "true", "yes"})
NO_RECEIPT_VALUES = frozenset({"", "0", "false"})
# Field limits of the National Tax Agency 医療費集計フォーム.
MAX_PERSON_CHARS = 10
MAX_PAYEE_CHARS = 20

# Columns B to J of the official form. Paste the rows at cell B9; column A (No) is a formula.
FORM_HEADER = [
    "医療を受けた人",
    "病院・薬局などの名称",
    "診療・治療",
    "医薬品購入",
    "介護保険サービス",
    "その他の医療費",
    "支払った医療費の金額",
    "左のうち、補填される金額",
    "支払年月日",
]

SUGGESTION_COLUMNS = ("row", "payee", "amount", "suggestion", "reason")
SUGGESTION_VALUES = ("include", "exclude", "unsure")
ANNOTATION_COLUMNS = ["llm_suggestion", "llm_reason", "llm_flag"]


class IryohiInputError(ValueError):
    """Raised when iryohi_raw or the suggestions file cannot be used as is."""


@dataclass(frozen=True)
class RawRow:
    sheet_row: int
    values: Dict[str, str]


@dataclass(frozen=True)
class FormRow:
    sheet_row: int
    person: str
    payee: str
    shinryo: bool
    iyakuhin: bool
    kaigo: bool
    other: bool
    amount: int
    refund: int
    date: datetime.date


@dataclass(frozen=True)
class Finding:
    sheet_row: int
    message: str


@dataclass(frozen=True)
class ShukeiForm:
    rows: List[FormRow]
    findings: List[Finding]
    total_amount: int
    total_refund: int


@dataclass(frozen=True)
class Suggestion:
    sheet_row: int
    payee: str
    amount: int
    suggestion: str
    reason: str


@dataclass(frozen=True)
class AnnotateStats:
    agree: int
    disagree: int
    unsure: int
    missing: int


def _read_csv_dicts(path: Union[str, Path]) -> Tuple[List[str], List[Dict[str, str]]]:
    reader = csv.DictReader(io.StringIO("\n".join(read_csv_lines(path))))
    records = [{k: (v or "") for k, v in record.items()} for record in reader]
    return list(reader.fieldnames or []), records


def _is_true(value: str) -> bool:
    return value.strip().lower() in TRUE_VALUES


def _parse_yen(value: str, column: str, sheet_row: int) -> int:
    cleaned = value.strip().replace(",", "").replace("¥", "")
    if cleaned == "":
        return 0
    if not re.fullmatch(r"\d+", cleaned):
        raise IryohiInputError(f"row {sheet_row}: {column} '{value}' is not a whole yen amount")
    return int(cleaned)


def read_iryohi_raw(path: Union[str, Path]) -> Tuple[List[str], List[RawRow]]:
    """Read the iryohi_raw CSV. Returns the header and the rows numbered like the sheet."""
    header, records = _read_csv_dicts(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise IryohiInputError(f"{path}: missing columns: {', '.join(missing)}")
    return header, [RawRow(sheet_row=i + 2, values=record) for i, record in enumerate(records)]


def _row_findings(row: RawRow, amount: int, refund: int) -> List[str]:
    v = row.values
    messages = []
    for column in CATEGORY_COLUMNS:
        value = v[column].strip()
        if value not in ("", CATEGORY_SELECTED):
            messages.append(f"{column} is '{value}', expected {CATEGORY_SELECTED} or empty; left empty in the form")
    if not any(v[c].strip() == CATEGORY_SELECTED for c in CATEGORY_COLUMNS):
        messages.append("no 医療費の区分 is selected")
    person, payee = v["iryouhikoujo_person"].strip(), v["iryouhikoujo_payee"].strip()
    if len(person) > MAX_PERSON_CHARS:
        messages.append(f"医療を受けた人 has {len(person)} characters, the form allows {MAX_PERSON_CHARS}")
    if len(payee) > MAX_PAYEE_CHARS:
        messages.append(f"病院・薬局などの名称 has {len(payee)} characters, the form allows {MAX_PAYEE_CHARS}")
    if v["iryouhikoujo_type"].strip() != TRANSPORT_TYPE and v["receipt"].strip().lower() in NO_RECEIPT_VALUES:
        messages.append("no receipt")
    if refund > amount:
        messages.append(f"refund {refund} is larger than the amount {amount}")
    if _is_true(v["need_data_fix"]):
        messages.append("need_data_fix is set")
    return messages


def build_shukei_form(rows: Sequence[RawRow]) -> ShukeiForm:
    """Keep rows with include set, map them to 医療費集計フォーム rows, and list what needs a look."""
    form_rows: List[FormRow] = []
    findings: List[Finding] = []
    for row in rows:
        v = row.values
        if not _is_true(v["include"]):
            continue
        amount = _parse_yen(v["iryouhikoujo_amount"], "iryouhikoujo_amount", row.sheet_row)
        refund = _parse_yen(v["iryouhikoujo_refund"], "iryouhikoujo_refund", row.sheet_row)
        try:
            date = parse_flexible_date(v["iryouhikoujo_date"])
        except ValueError as e:
            raise IryohiInputError(f"row {row.sheet_row}: iryouhikoujo_date: {e}") from e
        form_rows.append(
            FormRow(
                sheet_row=row.sheet_row,
                person=v["iryouhikoujo_person"].strip(),
                payee=v["iryouhikoujo_payee"].strip(),
                shinryo=v["is_type_shinryo"].strip() == CATEGORY_SELECTED,
                iyakuhin=v["is_type_iyakuhin"].strip() == CATEGORY_SELECTED,
                kaigo=v["is_type_kaigo"].strip() == CATEGORY_SELECTED,
                other=v["is_type_other"].strip() == CATEGORY_SELECTED,
                amount=amount,
                refund=refund,
                date=date,
            )
        )
        findings.extend(Finding(row.sheet_row, m) for m in _row_findings(row, amount, refund))

    years = Counter(v.values["year"].strip() for v in rows if _is_true(v.values["include"]))
    if len(years) > 1:
        main_year = years.most_common(1)[0][0]
        for row in rows:
            year = row.values["year"].strip()
            if _is_true(row.values["include"]) and year != main_year:
                findings.append(Finding(row.sheet_row, f"year is {year}, most rows are {main_year}"))

    return ShukeiForm(
        rows=form_rows,
        findings=findings,
        total_amount=sum(r.amount for r in form_rows),
        total_refund=sum(r.refund for r in form_rows),
    )


def form_table(form: ShukeiForm) -> List[List[object]]:
    """Header plus one row per form entry, in the column order of the official form (B to J)."""

    def mark(selected: bool) -> str:
        return CATEGORY_SELECTED if selected else ""

    table: List[List[object]] = [list(FORM_HEADER)]
    for r in form.rows:
        table.append(
            [r.person, r.payee, mark(r.shinryo), mark(r.iyakuhin), mark(r.kaigo), mark(r.other),
             r.amount, r.refund, r.date.isoformat()]
        )
    return table


def read_suggestions(path: Union[str, Path]) -> List[Suggestion]:
    """Read review suggestions: row, payee, amount, suggestion (include/exclude/unsure), reason."""
    header, records = _read_csv_dicts(path)
    missing = [c for c in SUGGESTION_COLUMNS if c not in header]
    if missing:
        raise IryohiInputError(f"{path}: missing columns: {', '.join(missing)}")

    suggestions: List[Suggestion] = []
    seen = set()
    for record in records:
        row_text = record["row"].strip()
        if not row_text.isdigit():
            raise IryohiInputError(f"{path}: row '{row_text}' is not a row number")
        sheet_row = int(row_text)
        if sheet_row in seen:
            raise IryohiInputError(f"row {sheet_row}: more than one suggestion")
        seen.add(sheet_row)
        value = record["suggestion"].strip().lower()
        if value not in SUGGESTION_VALUES:
            raise IryohiInputError(
                f"row {sheet_row}: suggestion '{record['suggestion']}' must be include, exclude, or unsure"
            )
        suggestions.append(
            Suggestion(
                sheet_row=sheet_row,
                payee=record["payee"].strip(),
                amount=_parse_yen(record["amount"], "amount", sheet_row),
                suggestion=value,
                reason=record["reason"].strip(),
            )
        )
    return suggestions


def annotate(
    header: List[str], rows: Sequence[RawRow], suggestions: Sequence[Suggestion]
) -> Tuple[List[str], List[List[str]], AnnotateStats]:
    """Append llm_suggestion, llm_reason, and llm_flag to every row.

    llm_flag is 1 when the suggestion is unsure or disagrees with the include column, so a person
    checks those rows first. Each suggestion must name the payee and amount of its row, which
    catches suggestions written against a shifted or different sheet.
    """
    by_row = {r.sheet_row: r for r in rows}
    for s in suggestions:
        row = by_row.get(s.sheet_row)
        if row is None:
            raise IryohiInputError(f"row {s.sheet_row}: no such row in iryohi_raw")
        payee = row.values["iryouhikoujo_payee"].strip()
        amount = _parse_yen(row.values["iryouhikoujo_amount"], "iryouhikoujo_amount", s.sheet_row)
        if (s.payee, s.amount) != (payee, amount):
            raise IryohiInputError(
                f"row {s.sheet_row}: suggestion is for {s.payee} {s.amount}, but the row is {payee} {amount}"
            )

    suggestion_by_row = {s.sheet_row: s for s in suggestions}
    counts = Counter()
    out_rows: List[List[str]] = []
    for row in rows:
        values = [row.values.get(h, "") for h in header]
        s = suggestion_by_row.get(row.sheet_row)
        if s is None:
            counts["missing"] += 1
            out_rows.append(values + ["", "", ""])
            continue
        if s.suggestion == "unsure":
            kind = "unsure"
        elif (s.suggestion == "include") == _is_true(row.values["include"]):
            kind = "agree"
        else:
            kind = "disagree"
        counts[kind] += 1
        out_rows.append(values + [s.suggestion, s.reason, "" if kind == "agree" else "1"])

    stats = AnnotateStats(
        agree=counts["agree"], disagree=counts["disagree"], unsure=counts["unsure"], missing=counts["missing"]
    )
    return header + ANNOTATION_COLUMNS, out_rows, stats
