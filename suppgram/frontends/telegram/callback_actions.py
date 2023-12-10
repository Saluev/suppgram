from enum import Enum


class CallbackActionKind(str, Enum):
    # common
    PAGE = "page"

    # customer frontend
    RATE = "rate"

    # manager frontend
    ASSIGN_TO_ME = "assign_to_me"
    ADD_CONVERSATION_TAG = "add_tag"
    REMOVE_CONVERSATION_TAG = "remove_tag"
