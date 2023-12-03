from suppgram.entities import WorkplaceIdentification, AgentIdentification


class NoStorageSpecified(Exception):
    pass


class NoFrontendSpecified(Exception):
    pass


class AgentException(Exception):
    def __init__(self, identification: AgentIdentification):
        self.identification = identification


class AgentNotFound(AgentException):
    pass


class AgentAlreadyExists(AgentException):
    pass


class WorkplaceNotFound(Exception):
    def __init__(self, identification: WorkplaceIdentification):
        self.identification = identification


class WorkplaceAlreadyAssigned(Exception):
    pass


class CustomerNotFound(Exception):
    pass


class ConversationNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass


class DataNotFetched(RuntimeError):
    pass
