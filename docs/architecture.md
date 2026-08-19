# MaderaFlow Architecture

## Purpose

MaderaFlow demonstrates a multilingual voice-support workflow for wood drying
and cross-border logistics coordination. ElevenLabs provides speech and
conversation orchestration. FastAPI remains the authoritative boundary for
caller assignments, operational records, role-specific disclosure, language
selection, and escalation decisions.

All records in this repository are sample data. The system is not connected to
live customers, measurements, ticketing, telephony, or logistics systems.

The repository also contains an isolated first milestone for a Maderera Las
Garzas after-hours order-intake agent. It is based on a real workflow but is
disabled in production until durable storage and notification delivery exist.
No real order or contact record is committed to source control.

## System context

```mermaid
flowchart LR
    Caller[Caller]
    ElevenLabs[ElevenLabs agent]
    Webhook[POST /support-requests]
    API[MaderaFlow FastAPI]
    Config[Validated JSON configuration]

    Caller -->|English, Spanish, Portuguese| ElevenLabs
    ElevenLabs -->|Bearer-authenticated JSON| Webhook
    Webhook --> API
    API --> Config
    API -->|role-scoped spoken_message| ElevenLabs
    ElevenLabs -->|voice response| Caller
```

## Request sequence

```mermaid
sequenceDiagram
    participant C as Caller
    participant E as ElevenLabs
    participant A as FastAPI

    C->>E: Provides caller ID
    E->>A: caller_id + language
    A->>A: Identify role and assigned lots
    A-->>E: available_lots + ask_for_lot
    E-->>C: Ask for a three-digit lot number
    C->>E: Selects lot 204
    E->>A: caller_id + lot_id + language
    A->>A: Verify assignment and infer intent
    A-->>E: Role-specific spoken_message
    E-->>C: Speak response
```

If exactly one lot is assigned, FastAPI can skip the selection question. With
several assigned lots, choosing a lot is unavoidable because a 1:N relationship
does not identify one unique record.

## Component responsibilities

| Component | Responsibility | Must not do |
| --- | --- | --- |
| ElevenLabs | Speech recognition, language switching, conversational turns, tool calls | Invent operational facts or decide authorization |
| FastAPI routes | HTTP validation, authentication dependency, safe request logging | Contain business-specific response wording |
| Repository layer | Normalize approved aliases and resolve caller/lot/transport relationships | Decide what a role may hear |
| Support service | Infer intent, apply role disclosure, translate responses, calculate escalation | Access external services |
| Configuration layer | Load and validate sample records and foreign-key-style references | Store secrets or real customer data |

## After-hours order-intake subsystem

```mermaid
flowchart LR
    Caller[Peru or Germany caller]
    Phone[Inbound number and time routing]
    Agent[Separate ElevenLabs order agent]
    Orders[POST /order-requests]
    Rules[Conditional intake and escalation]
    Store[(Local SQLite milestone)]
    Outbox[Pending WhatsApp notification]

    Caller --> Phone
    Phone -->|outside working hours| Agent
    Agent -->|confirmed structured request| Orders
    Orders --> Rules
    Rules --> Store
    Store --> Outbox
```

`conversation_id` is an idempotency key: repeating the same webhook request
returns the existing request number instead of creating a duplicate. The local
SQLite repository demonstrates transactions and sequencing without another
package. It is not durable on a free Render filesystem and must be replaced by
managed storage or attached to a persistent disk before real calls are enabled.

WhatsApp uses an outbox boundary. Saving an order and delivering a notification
are different events, so the API reports both honestly. A request is not marked
processed until delivery is confirmed or a visible delivery-failure alert
exists.

## Code structure

```text
main.py                         Stable Uvicorn/Render entry point
maderaflow/
    api.py                      FastAPI app, middleware, dependencies, routes
    config.py                   Environment and validated configuration
    models.py                   API request models and shared types
    errors.py                   Framework-independent domain errors
    repositories.py             Identifier and assignment lookup
    support.py                  Business rules and multilingual responses
    order_intake.py             Multilingual order rules and escalation
    order_storage.py            Idempotent SQLite request persistence
config/maderaflow.json          Editable sample business records
config/order_intake.json        Public order-intake rules without secrets
tests/test_main.py              HTTP and architecture regression tests
tests/test_order_intake.py      Order-intake and privacy regression tests
```

Dependencies point inward: `api` calls `support` and `repositories`; those
modules use `config` and `models`. The configuration layer does not import the
web framework. This keeps business behavior testable without binding it to an
HTTP route.

## Trust boundaries

The webhook is protected by a bearer token stored independently in Render and
ElevenLabs. The token authenticates the integration, not the human caller.
Caller IDs therefore provide demonstration context, not production identity.

FastAPI verifies that the requested lot is assigned to the recognized caller
before building a response. Transport responses exclude buyer, procurement,
price, moisture, and completion information. Logs contain route templates and
status metadata but omit request bodies, query strings, caller IDs, and lot IDs.

## Current limitations

- JSON provides no transactional writes, concurrent updates, or history.
- Caller IDs are spoken context rather than authenticated identities.
- The shared bearer token protects one integration, not individual callers.
- Ticket creation and human transfer are recommendations only.
- Completion dates and moisture values are fixed recorded samples.
- Translations are maintained in Python and require a deployment to change.

These limitations are intentional for the current milestone and are recorded in
the architecture decisions rather than hidden.
