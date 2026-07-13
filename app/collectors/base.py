from abc import ABC
from abc import abstractmethod


class BaseCollector(ABC):
    """Abstract base class for all data collectors in the ingestion pipeline."""

    @abstractmethod
    def collect(self) -> list:
        """Collects articles from configured data sources.

        Returns:
            list: A list of collected Article objects.
        """
        pass