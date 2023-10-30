from suppgram.entities import WorkplaceIdentification


class AgentNotFound(Exception):
    def __init__(self, identification: WorkplaceIdentification):
        self.identification = identification


class ConversationNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass
