import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from finlog.cli import main

# Real 2025 inputs and MURC rates, kept out of git under user_data/ (see tests/test_tax_golden.py).
GOLDEN_2025 = Path("user_data/tax_golden/2025")

pytestmark = pytest.mark.skipif(not GOLDEN_2025.exists(), reason=f"{GOLDEN_2025} is not available")


def test_cli_tax_gsu_with_2025_inputs(tmp_path):
    """finlog tax gsu runs offline on the 2025 inputs and writes the year-end carryover."""
    fx_cache = tmp_path / "fx_cache.csv"
    shutil.copy(GOLDEN_2025 / "fx_rates.csv", fx_cache)
    output_carryover_file = tmp_path / "carryover_2025.json"
    runner = CliRunner()

    with patch("finlog.io.sheets_writer.HAS_GSPREAD", False), patch(
        "finlog.tax.fx_provider.DEFAULT_CACHE_PATH", fx_cache
    ):
        result = runner.invoke(
            main,
            [
                "tax",
                "gsu",
                "--vests",
                str(GOLDEN_2025 / "vests.csv"),
                "--dividend",
                str(GOLDEN_2025 / "dividend.csv"),
                "--sales",
                str(GOLDEN_2025 / "sales.csv"),
                "--carryover",
                str(GOLDEN_2025 / "carryover_2024.json"),
                "--output-carryover",
                str(output_carryover_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Tax Calculation Summary:" in result.output
    assert "Total Vest Salary Income (給与所得):" in result.output
    assert output_carryover_file.exists()
