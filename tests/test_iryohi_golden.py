"""Golden test: the 医療費集計フォーム built from the 2025 iryohi_raw must match what was submitted.

Inputs are personal data under user_data/tax_golden/2025/ (ignored by git):
    iryohi_raw.csv        # the reviewed iryohi_raw tab of the 2025 確定申告 sheet
    iryohi_submitted.csv  # the iryohi_submitted tab (rows pasted into the official form)
    iryohi_expected.json  # row count, totals, and rows with a known category typo
"""

import csv
import json
from pathlib import Path

import pytest

from finlog.tax.iryohi import build_shukei_form, form_table, read_iryohi_raw

GOLDEN_2025 = Path("user_data/tax_golden/2025")

pytestmark = pytest.mark.skipif(
    not (GOLDEN_2025 / "iryohi_expected.json").exists(), reason="2025 iryohi golden data is not available"
)


@pytest.fixture
def expected_2025():
    return json.loads((GOLDEN_2025 / "iryohi_expected.json").read_text(encoding="utf-8"))


@pytest.fixture
def form_2025():
    _, rows = read_iryohi_raw(GOLDEN_2025 / "iryohi_raw.csv")
    return build_shukei_form(rows)


@pytest.fixture
def submitted_2025():
    with open(GOLDEN_2025 / "iryohi_submitted.csv", encoding="utf-8", newline="") as f:
        return [
            [r["person"], r["payee"], r["shinryo"], r["iyakuhin"], r["kaigo"], r["other"],
             int(r["amount"]), int(r["refund"]), r["date"]]
            for r in csv.DictReader(f)
        ]


def test_2025_total_matches_submitted_total(form_2025, expected_2025):
    assert len(form_2025.rows) == expected_2025["form_rows"]
    assert form_2025.total_amount == expected_2025["total_amount"]
    assert form_2025.total_refund == expected_2025["total_refund"]


def test_2025_form_rows_match_submitted_rows(form_2025, submitted_2025, expected_2025):
    """Rows with a category typo were submitted with the bad value; export leaves it empty instead."""
    table = form_table(form_2025)[1:]
    typo_rows = set(expected_2025["category_typo_rows"])

    assert len(table) == len(submitted_2025)
    for form_row, built, submitted in zip(form_2025.rows, table, submitted_2025):
        if form_row.sheet_row in typo_rows:
            assert built == submitted[:2] + [""] + submitted[3:], f"sheet row {form_row.sheet_row}"
        else:
            assert built == submitted, f"sheet row {form_row.sheet_row}"


def test_2025_findings_report_category_typos(form_2025, expected_2025):
    typo_findings = {f.sheet_row for f in form_2025.findings if f.message.startswith("is_type_shinryo is ")}

    assert typo_findings == set(expected_2025["category_typo_rows"])
