from abc import ABC, abstractmethod


class BaseSimilarityStrategy(ABC):
    """Abstract Base Class for merchant text similarity strategies."""

    @abstractmethod
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two merchant strings (0.0 to 1.0)."""
        pass
