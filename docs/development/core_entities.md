# Core entities

Core entities listed here are used in backend-storage and backend-frontend communication.
For simplicity reasons, they are all designed to be simple frozen dataclasses. If you are
implementing your own Suppgram frontend, you may need to extend these classes with new fields.

## Customers

::: suppgram.entities.Customer
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.CustomerIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.CustomerDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false

## Agents

::: suppgram.entities.Agent
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.AgentIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.AgentDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false


## Agent workplaces

::: suppgram.entities.Workplace
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.WorkplaceIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false

## Conversations

::: suppgram.entities.Conversation
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.ConversationDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.ConversationState
    handler: python
    options:
      show_root_heading: true
      show_source: false
      show_if_no_docstring: true

::: suppgram.entities.Message
    handler: python
    options:
      show_root_heading: true
      show_source: false

::: suppgram.entities.MessageKind
    handler: python
    options:
      show_root_heading: true
      show_source: false
      show_if_no_docstring: true

::: suppgram.entities.ConversationTag
    handler: python
    options:
      show_root_heading: true
      show_source: false
