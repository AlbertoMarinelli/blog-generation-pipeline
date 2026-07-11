from abc import ABC
from abc import abstractmethod


class BaseCollector(ABC):

    @abstractmethod
    def collect(self):
        pass