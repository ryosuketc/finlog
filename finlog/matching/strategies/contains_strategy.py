import difflib
import json
from pathlib import Path
import re
import unicodedata
from typing import Dict, List, Optional
from finlog.matching.strategies.base import BaseSimilarityStrategy


class SimpleContainsStrategy(BaseSimilarityStrategy):
    """Simple similarity strategy using merchant alias mapping, NFKC normalization, containment, and difflib."""

    def __init__(self, merchant_map: Optional[Dict[str, List[str]]] = None):
        if merchant_map is None:
            merchant_map = self._load_default_merchant_map()
        self.merchant_map = merchant_map
        self.alias_to_canonical = self._build_alias_index(merchant_map)

    def _load_default_merchant_map(self) -> Dict[str, List[str]]:
        default_map_path = Path(__file__).parent.parent / "merchant_map.json"
        if default_map_path.exists():
            try:
                with open(default_map_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _build_alias_index(self, merchant_map: Dict[str, List[str]]) -> Dict[str, str]:
        index: Dict[str, str] = {}
        for canonical, aliases in merchant_map.items():
            norm_canonical = self.basic_normalize(canonical)
            if norm_canonical:
                index[norm_canonical] = canonical.lower()
            for alias in aliases:
                norm_alias = self.basic_normalize(alias)
                if norm_alias:
                    index[norm_alias] = canonical.lower()
        return index

    def basic_normalize(self, text: str) -> str:
        if not text:
            return ""
        # NFKC Unicode normalization & lowercase
        s = unicodedata.normalize("NFKC", str(text)).lower()
        # Strip common card transaction noise
        s = re.sub(r"/(id|ic|visa|jcb)|\[通販\]|マーケットプレイス|\(モバイル\)|株式会社|支店|店", "", s)
        return s.strip()

    def normalize(self, text: str) -> str:
        s = self.basic_normalize(text)
        if not s:
            return ""

        # Check alias mapping
        if s in self.alias_to_canonical:
            return self.alias_to_canonical[s]

        for alias, canonical in self.alias_to_canonical.items():
            if alias and (alias in s or s in alias):
                return canonical

        return s

    def similarity(self, text1: str, text2: str) -> float:
        n1 = self.normalize(text1)
        n2 = self.normalize(text2)

        if not n1 or not n2:
            return 0.5

        # Substring containment check
        if n1 in n2 or n2 in n1:
            return 1.0

        # difflib fallback
        return difflib.SequenceMatcher(None, n1, n2).ratio()

