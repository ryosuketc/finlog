import csv
import datetime
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from finlog.models.tax import FXRateRecord


DEFAULT_CACHE_PATH = Path("user_data/fx_cache.csv")

# Mitsubishi UFJ Research and Consulting (MURC) historical rate page, the source cited in past tax returns.
MURC_URL = "https://www.murc-kawasesouba.jp/fx/past_3month_result.php?y={y}&m={m}&d={d}"
MURC_SOURCE = "MURC"
# The USD row is ASCII, so match bytes and skip decoding (the page is Japanese-encoded).
_MURC_USD_ROW = re.compile(
    rb">\s*USD\s*</td>\s*"
    rb"<td[^>]*>\s*([\d.]+)\s*</td>\s*"
    rb"<td[^>]*>\s*([\d.]+)\s*</td>\s*"
    rb"<td[^>]*>\s*([\d.]+)\s*</td>"
)
# Target date plus 6 preceding days covers weekends and the longest Japanese holiday runs.
MAX_LOOKBACK_DAYS = 7


class FXRateUnavailableError(Exception):
    """Raised when no source returns a USD/JPY rate for a date."""


def parse_murc_usd(html: bytes) -> Optional[Tuple[Decimal, Decimal, Decimal]]:
    """Return (TTS, TTB, TTM) for USD from a MURC rate page, or None if the page has no USD row."""
    match = _MURC_USD_ROW.search(html)
    if match is None:
        return None
    tts, ttb, ttm = (Decimal(v.decode("ascii")) for v in match.groups())
    return tts, ttb, ttm


def _urllib_get(url: str) -> bytes:
    """GET url and return the body. Raises OSError (including URLError) on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "finlog/0.1.0"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read()


class FXProvider:
    """USD/JPY daily rates (TTM, TTS, TTB) from MURC, with Frankfurter as a fallback, cached in a CSV file."""

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        use_cache: bool = True,
        http_get: Optional[Callable[[str], bytes]] = None,
    ):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.use_cache = use_cache
        self.http_get = http_get or _urllib_get
        self.cache: Dict[datetime.date, FXRateRecord] = {}
        if self.use_cache:
            self._load_cache()

    def _load_cache(self) -> None:
        """Load existing cached rates from CSV if available."""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row.get("date") or not row.get("ttm"):
                        continue
                    d = datetime.date.fromisoformat(row["date"].strip())
                    ttm = Decimal(row["ttm"].strip())
                    tts = Decimal(row["tts"].strip()) if row.get("tts") else ttm + Decimal("1.0")
                    ttb = Decimal(row["ttb"].strip()) if row.get("ttb") else ttm - Decimal("1.0")
                    source = row.get("source", "cache").strip()
                    self.cache[d] = FXRateRecord(date=d, ttm=ttm, tts=tts, ttb=ttb, source=source)
        except Exception as e:
            print(f"[Warning] Failed to load FX cache from {self.cache_path}: {e}")

    def save_cache(self) -> None:
        """Save cached FX rates back to CSV file."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        sorted_records = sorted(self.cache.values(), key=lambda r: r.date)
        with open(self.cache_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "ttm", "tts", "ttb", "source"])
            for r in sorted_records:
                writer.writerow([r.date.isoformat(), str(r.ttm), str(r.tts), str(r.ttb), r.source])

    def get_rate(self, target_date: datetime.date) -> FXRateRecord:
        """Get FXRateRecord (TTM, TTS, TTB) for target_date from cache, MURC, or Frankfurter.

        Only cached MURC rates are reused. Rates cached from other sources are fetched again,
        so earlier Frankfurter rates are replaced by MURC rates once MURC is reachable.
        """
        cached = self.cache.get(target_date) if self.use_cache else None
        if cached and cached.source.startswith(MURC_SOURCE):
            return cached

        rate_record = self._fetch_from_murc(target_date) or self._fetch_from_frankfurter(target_date)
        if rate_record is None:
            raise FXRateUnavailableError(
                f"No USD/JPY rate for {target_date.isoformat()} or the {MAX_LOOKBACK_DAYS - 1} days before it "
                "from MURC or Frankfurter."
            )
        if self.use_cache:
            self.cache[target_date] = rate_record
            self.save_cache()
        return rate_record

    def _lookback_dates(self, target_date: datetime.date):
        """Yield target_date and the preceding days, for weekends and holidays."""
        for offset in range(MAX_LOOKBACK_DAYS):
            yield target_date - datetime.timedelta(days=offset)

    def _fetch_from_murc(self, target_date: datetime.date) -> Optional[FXRateRecord]:
        """Fetch the MURC published rate, falling back to preceding business days."""
        for curr_date in self._lookback_dates(target_date):
            url = MURC_URL.format(y=curr_date.year, m=curr_date.month, d=curr_date.day)
            try:
                rates = parse_murc_usd(self.http_get(url))
            except OSError:
                continue
            if rates is None:
                continue
            tts, ttb, ttm = rates
            source = MURC_SOURCE if curr_date == target_date else f"{MURC_SOURCE} ({curr_date.isoformat()})"
            return FXRateRecord(date=target_date, ttm=ttm, tts=tts, ttb=ttb, source=source)
        return None

    def _fetch_from_frankfurter(self, target_date: datetime.date) -> Optional[FXRateRecord]:
        """Fetch the ECB reference rate from Frankfurter as TTM, with TTS/TTB = TTM +/- 1 JPY."""
        for curr_date in self._lookback_dates(target_date):
            date_str = curr_date.isoformat()
            url = f"https://api.frankfurter.app/{date_str}?from=USD&to=JPY"
            try:
                data = json.loads(self.http_get(url).decode("utf-8"))
            except (OSError, ValueError):
                continue
            jpy = data.get("rates", {}).get("JPY")
            if jpy is None:
                continue
            ttm = Decimal(str(jpy))
            source = "Frankfurter API" if curr_date == target_date else f"Frankfurter API ({date_str})"
            return FXRateRecord(
                date=target_date, ttm=ttm, tts=ttm + Decimal("1.0"), ttb=ttm - Decimal("1.0"), source=source
            )
        return None
