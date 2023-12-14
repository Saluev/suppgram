from suppgram.entities import WorkplaceIdentification, AgentIdentification, CustomerIdentification


class NoStorageSpecified(Exception):
    pass


class NoFrontendSpecified(Exception):
    pass


class AgentException(Exception):
    def __init__(self, identification: AgentIdentification):
        self.identification = identification


class AgentEmptyIdentification(AgentException):
    def __str__(self):
        return (
            f"received agent identification {self.identification} without supported non-null fields"
        )


class AgentNotFound(AgentException):
    pass


class AgentDeactivated(AgentException):
    pass


class WorkplaceException(Exception):
    def __init__(self, identification: WorkplaceIdentification):
        self.identification = identification


class WorkplaceEmptyIdentification(WorkplaceException):
    def __str__(self):
        return f"received workplace identification {self.identification} without supported non-null fields"


class WorkplaceNotFound(WorkplaceException):
    pass


class TagAlreadyExists(Exception):
    pass


class ConversationAlreadyAssigned(Exception):
    pass


class CustomerException(Exception):
    def __init__(self, identification: CustomerIdentification):
        self.identification = identification


class CustomerNotFound(CustomerException):
    pass


class CustomerEmptyIdentification(CustomerException):
    def __str__(self):
        return f"received customer identification {self.identification} without supported non-null fields"


class ConversationNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass


class DataNotFetched(RuntimeError):
    pass
