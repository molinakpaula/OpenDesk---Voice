# ElevenLabs Integration Contract

This document describes how the demonstration ElevenLabs agent interacts with
the fictional MaderaFlow API. ElevenLabs is configured to call the protected
webhook directly, so this repository does not need an ElevenLabs SDK. API keys,
bearer-token values, and other secrets are never stored in the repository.

Every organization, caller, and wood lot described here is fictional.

## Agent identity and disclosure

The agent name is **MaderaFlow Support**. At the beginning of a conversation it
must identify itself as an automated voice assistant. It must not pretend to be
a human employee.

The current opening messages and public capabilities are available from:

```http
GET /voice-agent-config
```

## Conversation flow

```text
Caller speaks
  -> voice layer identifies language and gathers caller ID, lot ID, and intent
  -> voice layer calls POST /support-requests
  -> API validates fictional context and applies role/privacy rules
  -> voice layer speaks only the returned spoken_message
  -> unresolved request becomes a human handoff or ticket recommendation
```

The voice layer should ask a clarifying question when a required value is
missing. It must not guess a caller ID, lot ID, measurement, or operational fact.

## API tool definition

Tool name: `get_maderaflow_support_response`

Method and path:

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
      "enum": ["US-BUYER-001", "PE-SUPPLIER-001", "BR-LOGISTICS-001"],
      "description": "Canonical fictional caller ID. Convert only an approved spoken alias from the agent prompt to one of these values."
    },
    "lot_id": {
      "type": "string",
      "enum": ["MF-204", "MF-317", "MF-422"],
      "description": "Canonical fictional MaderaFlow lot ID. Spoken forms such as lot 204 must be mapped to the matching value."
    },
    "intent": {
      "type": "string",
      "enum": [
        "check_lot_status",
        "check_documentation",
        "check_transport_readiness"
      ]
    }
  },
  "required": ["caller_id", "lot_id", "intent"]
}
```

The voice layer should speak `spoken_message` exactly as the authoritative
operational answer. Structured fields are for control flow and display, not for
inventing extra spoken details.

## Bearer-token setup

The operational endpoint requires one shared secret. Never put its value in
this repository, a prompt, a conversation, or a support message.

1. Generate a random token locally.
2. Add it to Render as `MADERAFLOW_TOOL_TOKEN`.
3. In the ElevenLabs webhook tool, add the `Authorization` header, select
   **Secret**, and store the value as `Bearer <your token>`.

The same token value must be used on both sides. Public endpoints such as
`/health` and `/voice-agent-config` do not require it.

## Intent and role mapping

| Intent | Allowed caller type | Returned context |
| --- | --- | --- |
| `check_lot_status` | Buyer | Drying, recorded moisture, estimate, shipment readiness |
| `check_documentation` | Supplier | Receipt, documents, supplier action |
| `check_transport_readiness` | Transport partner | Collection, destination, scheduling |

If the intent is unknown or unavailable for the caller's role, the API returns
`resolved: false` and a localized safe next step.

## Handoff and ticket routing

Fictional support hours are Monday–Friday, 08:00–18:00 in `America/Lima`.
Holidays are not modeled.

- During support hours, use `next_action: human_handoff` to transfer to a human.
- Outside support hours, explain that a ticket is recommended.
- `ticket_created: false` means no ticket exists yet. The voice layer must not
  claim that a ticket was created or provide an invented ticket number.

## Safety instructions for the voice agent

- Use only facts returned by the API.
- Say "latest recorded moisture," never "live moisture."
- Treat completion dates as estimates and never guarantees.
- Do not give legal or customs advice.
- Do not admit liability.
- Do not reveal information outside the caller's role.
- Do not disclose buyer or pricing details to transport partners.
- When the API cannot resolve a request, use its handoff or ticket guidance.

## English example

Caller: "This is US-BUYER-001. What is the status of lot MF-204?"

Tool request:

```json
{
  "caller_id": "US-BUYER-001",
  "lot_id": "MF-204",
  "intent": "check_lot_status"
}
```

The voice layer speaks the English `spoken_message` returned by the API,
including that the completion date is estimated and not guaranteed.

## Spanish example

Caller: "Soy PE-SUPPLIER-001. ¿Falta documentación para el lote MF-317?"

Tool request:

```json
{
  "caller_id": "PE-SUPPLIER-001",
  "lot_id": "MF-317",
  "intent": "check_documentation"
}
```

The response uses Spanish and describes only receipt, documentation, and the
fictional supplier action.

## Portuguese example

Caller: "Sou BR-LOGISTICS-001. O transporte do lote MF-422 pode ser agendado?"

Tool request:

```json
{
  "caller_id": "BR-LOGISTICS-001",
  "lot_id": "MF-422",
  "intent": "check_transport_readiness"
}
```

The response uses Portuguese and includes only collection readiness,
destination, and scheduling status—never buyer or pricing information.
