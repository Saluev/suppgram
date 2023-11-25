import abc


class CustomerFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass


class AgentFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass


class ManagerFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass
