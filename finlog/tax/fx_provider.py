import csv
import datetime
import json
import os
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from finlog.models.tax import FXRateRecord


DEFAULT_CACHE_PATH = Path("user_data/fx_cache.csv")


class FXProvider:
    """FX Rate provider supporting daily USD/JPY rates (TTM, TTS, TTB) with CSV caching and API fallback."""

    def __init__(self, cache_path: Optional[Path] = None, use_cache: bool = True):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.use_cache = use_cache
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
        """Get FXRateRecord (TTM, TTS, TTB) for target_date. Uses cache or fetches via API."""
        if self.use_cache and target_date in self.cache:
            return self.cache[target_date]

        rate_record = self._fetch_from_api(target_date)
        if self.use_cache:
            self.cache[target_date] = rate_record
            self.save_cache()
        return rate_record

    def _fetch_from_api(self, target_date: datetime.date) -> FXRateRecord:
        """Fetch rate from Frankfurter API with fallback to preceding business days for weekends/holidays."""
        curr_date = target_date
        max_attempts = 7

        for _ in range(max_attempts):
            date_str = curr_date.isoformat()
            url = f"https://api.frankfurter.app/{date_str}?from=USD&to=JPY"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "finlog/0.1.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        rates = data.get("rates", {})
                        if "JPY" in rates:
                            ttm = Decimal(str(rates["JPY"]))
                            tts = ttm + Decimal("1.0")
                            ttb = ttm - Decimal("1.0")
                            source = "Frankfurter API" if curr_date == target_date else f"Frankfurter API ({date_str})"
                            return FXRateRecord(date=target_date, ttm=ttm, tts=tts, ttb=ttb, source=source)
            except Exception:
                pass

            # Fallback to preceding day if weekend/holiday/API error
            curr_date -= datetime.timedelta(days=1)

        # Fallback rate if network is unavailable
        fallback_ttm = Decimal("150.00")
        return FXRateRecord(
            date=target_date,
            ttm=fallback_ttm,
            tts=fallback_ttm + Decimal("1.0"),
            ttb=fallback_ttm - Decimal("1.0"),
            source="Offline Fallback Default",
        )
