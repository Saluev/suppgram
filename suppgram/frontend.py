import abc


class CustomerFrontend(abc.ABC):
    """This component is responsible for interacting with the customers
    within some external system (e.g. Telegram)."""

    async def initialize(self):
        """Performs asynchronous initialization if needed."""

    @abc.abstractmethod
    async def start(self):
        """Starts serving the frontend, be it long polling loop or an HTTP server."""


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
