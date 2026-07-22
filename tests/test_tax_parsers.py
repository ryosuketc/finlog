import datetime
from decimal import Decimal
from finlog.parsers.tax import VestsParser, DividendParser, SalesParser


def test_vests_parser_sample_data():
    lines = [
        '"Alphabet, Inc. - GSUs (report run on ...)"',
        "Purno,Jurisdiction,Award Date,Vesting Date,GSUs Vested,Shares Deposited,Fair Market Value,Amount Subject to Tax Withholding,Total Tax Withheld at Broker,FX Rate,Currency,Release Type,Award Number",
        'RB8C3DD6B0,Japan,08-Mar-2023,25-Dec-2024,10.034,10.034,$197.57,"$1,982.42",$0.00,,USD,WCF,C1125704',
        'RB8C3DD687,Japan,05-Jan-2022,25-Dec-2024,40.137,40.137,$197.57,"$7,929.87",$0.00,,USD,WCF,C865869',
        '" 1. This is not an official tax document & is only for informational purposes. "',
    ]

    parser = VestsParser()
    records = parser.parse(lines)

    assert len(records) == 2
    r1 = records[0]
    assert r1.award_date == datetime.date(2023, 3, 8)
    assert r1.vesting_date == datetime.date(2024, 12, 25)
    assert r1.shares == Decimal("10.034")
    assert r1.fmv_usd == Decimal("197.57")


def test_dividend_parser_sample_data():
    lines = [
        "Entry Date,Activity,Type of Money,Cash,Number of Shares,Share Price,Book Value,Market Value",
        "2024-06-17,Dividend (Cash),Employee,19.8000,,,,",
        "2024-06-17,IRS Nonresident Alien Withholding,Employee,-5.9400,,,,",
        "2024-06-20,You bought,Employee,-13.8600,$0.08,$178.00,¥13.86,",
    ]

    parser = DividendParser()
    records = parser.parse(lines)

    assert len(records) == 3
    assert records[0].activity == "Dividend (Cash)"
    assert records[0].cash_usd == Decimal("19.8000")

    assert records[1].activity == "IRS Nonresident Alien Withholding"
    assert records[1].cash_usd == Decimal("-5.9400")

    assert records[2].activity == "You bought"
    assert records[2].shares == Decimal("0.08")
    assert records[2].share_price_usd == Decimal("178.00")


def test_sales_parser_sample_data():
    lines = [
        "Execution Date,Order Number,Plan,Type,Order Status,Price,Quantity,Net Amount,Net Share Proceeds,Tax Payment Method",
        '22-Feb-2024,WRC811F01F6-1EE,GSU Class C,Sale,Complete,$146.00,-92,"$13,431.89",0,N/A',
        '25-Mar-2024,WRC82486D46-1EE,GSU Class C,Sale,Complete,$150.80,-61,"$9,198.72",0,N/A',
        "Please note that any Alphabet share sales...",
    ]

    parser = SalesParser()
    records = parser.parse(lines)

    assert len(records) == 2
    r1 = records[0]
    assert r1.execution_date == datetime.date(2024, 2, 22)
    assert r1.price_usd == Decimal("146.00")
    assert r1.quantity == Decimal("92")
    assert r1.fee_usd == Decimal("0")


def test_sales_parser_with_fee():
    lines = [
        "Execution Date,Order Number,Plan,Type,Order Status,Price,Quantity,Net Amount,Fee",
        '22-Feb-2024,WRC811F01F6-1EE,GSU Class C,Sale,Complete,$146.00,-92,"$13,431.89",$15.50',
    ]

    parser = SalesParser()
    records = parser.parse(lines)

    assert len(records) == 1
    assert records[0].fee_usd == Decimal("15.50")
