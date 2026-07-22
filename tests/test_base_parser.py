import datetime
import pytest
from finlog.parsers.base import BaseParser


class DummyParser(BaseParser):
    def parse(self, lines):
        return []


def test_clean_amount():
    parser = DummyParser()
    assert parser.clean_amount("16,746") == 16746
    assert parser.clean_amount(10642) == 10642
    assert parser.clean_amount("-2,300") == -2300
    assert parser.clean_amount("0") == 0
    assert parser.clean_amount("") == 0
    assert parser.clean_amount(None) == 0


def test_clean_string():
    parser = DummyParser()
    assert parser.clean_string("  マクドナルド　 ") == "マクドナルド"
    assert parser.clean_string("ＡＭＡＺＯＮ") == "AMAZON"  # NFKC normalization
    assert parser.clean_string(None) == ""


def test_parse_date():
    parser = DummyParser()
    assert parser.parse_date("2026-05-20") == datetime.date(2026, 5, 20)
    assert parser.parse_date("2026/06/21") == datetime.date(2026, 6, 21)


def test_generate_transaction_id():
    parser = DummyParser()
    assert parser.generate_transaction_id("VISA", 1) == "VISA-00001"
    assert parser.generate_transaction_id("ZAIM", 42) == "ZAIM-00042"
