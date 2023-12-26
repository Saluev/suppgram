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
      heading_level: 3

::: suppgram.entities.CustomerIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.CustomerDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

<hr/>
## Agents

::: suppgram.entities.Agent
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.AgentIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.AgentDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

<hr/>
## Workplaces

::: suppgram.entities.Workplace
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.WorkplaceIdentification
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

<hr/>
## Conversations

::: suppgram.entities.Conversation
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.ConversationDiff
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.ConversationState
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.Message
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: suppgram.entities.MessageKind
    handler: python
    options:
      show_root_heading: true
      show_source: false
      show_if_no_docstring: true
      heading_level: 3

::: suppgram.entities.Tag
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
