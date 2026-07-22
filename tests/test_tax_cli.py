from click.testing import CliRunner
from finlog.cli import main


def test_cli_gsu_subcommand_sample_files(tmp_path):
    """Test finlog gsu subcommand with tax sample files."""
    runner = CliRunner()
    output_carryover_file = tmp_path / "carryover_2024.json"

    result = runner.invoke(
        main,
        [
            "gsu",
            "--vests",
            "user_data/tax_sample/tax_report_inputs - Vests.csv",
            "--dividend",
            "user_data/tax_sample/tax_report_inputs - Dividend.csv",
            "--sales",
            "user_data/tax_sample/tax_report_inputs - Sales.csv",
            "--output-carryover",
            str(output_carryover_file),
            "--use-cache",
        ],
    )

    assert result.exit_code == 0
    assert "Tax Calculation Summary:" in result.output
    assert "Total Vest Salary Income (給与所得):" in result.output
    assert "Total Capital Gains (譲渡所得):" in result.output
    assert output_carryover_file.exists()
