# ElevenLabs Integration Contract

This document describes how the MaderaFlow demonstration agent calls the
protected FastAPI webhook. The repository uses sample records only and contains
no real customer, employee, supplier, or shipment data.

## Caller-first conversation flow

```text
Caller gives caller ID
  -> ElevenLabs sends caller_id and active language
  -> API identifies the caller role and assigned wood lots
  -> one assigned lot: API can resolve it automatically
  -> several assigned lots: API returns available_lots and ask_for_lot
  -> caller selects the three-digit lot number
  -> API verifies the assignment and infers the role-specific intent
  -> ElevenLabs speaks only spoken_message
```

The API, rather than the language model, is responsible for role recognition,
lot authorization, and intent inference. This keeps the conversation simple and
prevents a caller from selecting an unrelated role or lot.

## Relationship model

`WOOD_LOT` is the central entity:

```text
BUYER       1 ----< N WOOD_LOT
PROVIDER    1 ----< N WOOD_LOT
WOOD_TYPE   1 ----< N WOOD_LOT
DRYING_STATUS 1 --< N WOOD_LOT

WOOD_LOT 1 ----< N TRANSPORT >---- 1 TRANSPORTER
```

A lot contains `buyer_id`, `provider_id`, `wood_type_id`, and
`drying_status_id`. It does not contain `transporter_id`. Transport is separate
because a lot can have an inbound movement to the drying facility followed by
an outbound movement to the buyer.

## API tool definition

Tool name: `get_maderaflow_support_response`

```http
POST /support-requests
Content-Type: application/json
Authorization: Bearer <secret stored in ElevenLabs>
```

Input schema:

```json
{
  "type": "object",
  "properties": {
    "caller_id": {
      "type": "string",
      "description": "Caller ID supplied by the caller. Ask for it if missing and never guess it."
    },
    "lot_id": {
      "type": "string",
      "description": "Optional selected lot ID. Omit it on the first call if the caller has not selected a lot."
    },
    "intent": {
      "type": "string",
      "enum": [
        "check_lot_status",
        "check_documentation",
        "check_transport_readiness"
      ],
      "description": "Optional because the API infers the intent from the assigned caller role."
    },
    "language": {
      "type": "string",
      "enum": ["en", "es", "pt"],
      "description": "Optional active conversation language. Defaults to the caller profile's preferred language."
    }
  },
  "required": ["caller_id"]
}
```

## Caller-only response

When a caller has several assigned lots, a request such as:

```json
{
  "caller_id": "US-BUYER-001",
  "language": "en"
}
```

returns control information similar to:

```json
{
  "resolved": false,
  "reason": "lot_selection_required",
  "next_action": "ask_for_lot",
  "available_lots": ["MF-204", "MF-317", "MF-422"],
  "spoken_message": "I found three assigned wood lots..."
}
```

ElevenLabs should speak `spoken_message`, collect one of those lot numbers, and
call the same tool again. It must not invent or select a lot for the caller.

## Resolved request

Once the caller chooses a lot, this minimal request is sufficient:

```json
{
  "caller_id": "US-BUYER-001",
  "lot_id": "MF-204",
  "language": "en"
}
```

The backend recognizes the caller as a buyer, verifies that the lot is assigned
to that buyer, and infers `check_lot_status`. Providers receive documentation
information, while transport partners receive only their relevant transport
movement, collection readiness, destination, and scheduling status.

## Authentication

The operational endpoint requires a shared bearer token. Never place the value
in this repository, a prompt, a conversation, or a support message.

1. Keep the token in Render as `MADERAFLOW_TOOL_TOKEN`.
2. Keep the matching value in the ElevenLabs secret used by the
   `Authorization` header.
3. Store the ElevenLabs value as `Bearer <your token>`.

## Handoff and ticket routing

Demonstration support hours are Monday–Friday, 08:00–18:00 in `America/Lima`.

- During support hours, `human_handoff` recommends a specialist.
- Outside support hours, `open_ticket` recommends a ticket.
- `ticket_created: false` means no ticket exists yet.

## Safety rules

- Speak only facts returned in `spoken_message`.
- Describe moisture as the latest recorded value, never as live.
- Treat completion dates as estimates, never guarantees.
- Do not provide legal or customs advice or admit liability.
- Do not reveal information outside the caller's assigned role and lots.
- Do not disclose buyer or pricing details to transport partners.
