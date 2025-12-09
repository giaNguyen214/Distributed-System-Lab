from abc import ABC, abstractmethod

class BasePlugin(ABC):
    def initialize(self, **kwargs):
        pass

    @abstractmethod
    def run(self, batch):
        pass

    def finalize(self):
        pass